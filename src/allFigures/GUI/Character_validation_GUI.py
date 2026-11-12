import queue
import threading
from io import BytesIO

from PIL import Image as PILImage, UnidentifiedImageError
import customtkinter
import requests
from PIL.SpiderImagePlugin import iforms
from ddgs.exceptions import DDGSException
from sqlalchemy import and_, column, true, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload
from CTkMessagebox import CTkMessagebox
from run import app as flask_app
from models.models import db, Figure, Character, CharacterAlias, Series
from ddgs import DDGS
import os
import concurrent.futures
from thefuzz import fuzz

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Referer": "https://www.google.com/"
}

class CharacterApp(customtkinter.CTk):
    def _get_imgs(self, character):
        for i in range(10):
            try:
                with DDGS() as ddgs:
                    # print("Extracting...")
                    raw_res = ddgs.images(f"{character.name} {character.series.title}", max_result = 5)
                    if raw_res:
                        # print("Success!!")
                        res=[row.get("image") for row in raw_res]
                        return res if res else None
            except DDGSException:
                print(f"Failed, retrying...")
        return None

    def _download_images(self, character):
        target_dir=os.path.join(os.getcwd(), "temp")
        os.makedirs(target_dir, exist_ok=True)
        file_path=os.path.join(target_dir, f"{character.name} - {character.S_ID}.png")
        if os.path.exists(file_path):
            print("image exists. skipping")
            return
        res = self._get_imgs(character)
        if res:
            for link in res:
                print(f"current char: {character.name}")
                print(f"downloading image: {link}")
                try:
                    response = requests.get(link, headers=headers, timeout=60)
                    if response.ok:
                        img=PILImage.open(BytesIO(response.content))
                        img=img.convert("RGB")
                        img.save(file_path)
                        print("image saved successfully.")
                        break
                except UnidentifiedImageError, requests.exceptions.RequestException:
                    continue




    def _fetch_from_db(self):
        with flask_app.app_context():
            query=db.session.query(Character)\
                .options(joinedload(Character.aliases))\
                .options(joinedload(Character.series))\
                .filter(Character.is_valid==0)\
                .order_by(Character.C_ID.asc())\
                .all()
            return query

    def _fetch_series(self, phrase):
        with flask_app.app_context():
            query=db.session.query(Series)\
            .filter(and_(Series.title.ilike(f"%{phrase}%"),
            Series.title.not_like(f"%{self.original_character.title}%"))).limit(25).all()
        return query

    def _confirm_char_choice(self, char):
        target_ch=next((ch for ch in self.chars_from_series if ch.C_ID==char.C_ID), None)
        if not self.first_ch:
            self.first_ch=target_ch
            if self.first_ch:
                self.chars_from_series.remove(self.first_ch)
                self._refresh_list(self.character_buttons, self.chars_from_series, self.char_scroll_frame)
                self.fst_textbox.insert(0.0, self.first_ch.name)
        else:
            if self.second_ch:
                self.snd_textbox.delete(0.0, "end")
                self.chars_from_series.append(self.second_ch)
                self.chars_from_series.sort(key=lambda d: d.C_ID)
            self.second_ch=target_ch
            if self.second_ch:
                self.chars_from_series.remove(self.second_ch)
                self._refresh_list(self.character_buttons, self.chars_from_series, self.char_scroll_frame)
                self.snd_textbox.insert(0.0, self.second_ch.name)
        self._reload_images()

        return

    def _refresh_list(self, button_list, dataset, target_frame):
        for btn in button_list:
            btn.destroy()
        button_list.clear()
        btn_texts={}
        if target_frame == self.suggestions_frame:
            dataset_ordered=sorted(dataset, key=lambda x:int(x.split(':')[1].split(',')[0]), reverse=True)
        else:
            for ch in dataset:
                if target_frame == self.char_scroll_frame:
                    score = fuzz.token_set_ratio(self.first_ch.name, ch.name) if self.first_ch else 0
                    btn_texts[ch]=f"{score}: {ch.name}"
                elif target_frame == self.alias_frame:
                    btn_texts[ch]=f"{ch.CA_ID} - {ch.alias}"
                elif target_frame == self.series_frame or target_frame==self.move_series_frame:
                    btn_texts[ch] = ch.title if ch.title else None
            if target_frame == self.char_scroll_frame:
                dataset_ordered=sorted(dataset, key=lambda x: int(btn_texts[x].split(":")[0]), reverse=True)
            else:
                dataset_ordered=dataset


        for ch in dataset_ordered:
            btn=customtkinter.CTkButton(
                target_frame,
                text=ch if (target_frame==self.suggestions_frame) else btn_texts[ch],
                anchor="w",
                fg_color="transparent",
                text_color=("black", "white"),
                hover_color=("gray70", "gray30"),
                command=(lambda v=ch: self._confirm_char_choice(v))
                if target_frame==self.char_scroll_frame else
                (lambda v=dataset[ch]: self._confirm_multiple_chars(v[0], v[1]))
                if target_frame==self.suggestions_frame else
                (lambda v=ch: self._merge_series(v))
                if target_frame == self.series_frame else
                (lambda v=ch: self._move_to_series(v))
                if target_frame==self.move_series_frame else
                None,
            )
            btn.pack(fill="x", pady=1)
            button_list.append(btn)

    def _move_to_series(self, series):
        alias_popup = CTkMessagebox(title="move??",
                                    message=f"Should current character be moved to {series.title}??",
                                    icon="question", option_1="Move", option_2="Back")
        response = alias_popup.get()
        if response=="Back":
            return
        if response=="Move":
            old_s_id = self.original_character.S_ID
            new_s_id = series.S_ID

            with flask_app.app_context():
                db_char = db.session.query(Character).get(self.original_character.C_ID)
                db_char.S_ID = new_s_id
                try:
                    db.session.commit()
                except:
                    db.session.rollback()
                    collision=db.session.query(Character)\
                        .filter(Character.S_ID==new_s_id,
                                Character.name==self.original_character.name)\
                        .first()
                    if collision:
                        query = text("CALL reassign_by_c_id(:old, :new)")
                        db.session.execute(query, {
                            "old": self.original_character.C_ID,
                            "new": collision.C_ID
                        })
                        db.session.commit()

                new_companions = db.session.query(Character) \
                    .options(joinedload(Character.series)) \
                    .filter(Character.S_ID == new_s_id, Character.C_ID != self.original_character.C_ID).all()
                db.session.expunge_all()
            self.original_character.S_ID = new_s_id
            self.chars_from_series = list(new_companions)

            temp_dir = os.path.join(os.getcwd(), "temp")
            old_img_path = os.path.join(temp_dir, f"{self.original_character.name}_{old_s_id}.png")
            new_img_path = os.path.join(temp_dir, f"{self.original_character.name}_{new_s_id}.png")
            if os.path.exists(old_img_path):
                os.rename(old_img_path, new_img_path)

            self._refresh_list(self.character_buttons, self.chars_from_series, self.char_scroll_frame)



    def _merge_series(self, series):
        alias_popup=CTkMessagebox(title="Merge??", message=f"Should current series become an alias of {series.title}??",
                                  icon="question", option_1="Merge", option_2="Back")
        response=alias_popup.get()
        if response=="Back":
            return
        if response=="Merge":
            old_s_id = self.original_character.S_ID
            new_s_id = series.S_ID
            with flask_app.app_context():
                query = text("CALL merge_series(:old, :new)")
                db.session.execute(query, {
                    "old": self.original_character.S_ID,
                    "new": series.S_ID
                })
                db.session.commit()

                new_companions = db.session.query(Character) \
                    .options(joinedload(Character.series)) \
                    .filter(Character.S_ID == new_s_id, Character.C_ID != self.original_character.C_ID).all()
                db.session.expunge_all()

            self.original_character.S_ID = new_s_id
            self.chars_from_series = list(new_companions)
            temp_dir = os.path.join(os.getcwd(), "temp")
            if os.path.exists(temp_dir):
                for filename in os.listdir(temp_dir):
                    if filename.endswith(f"_{old_s_id}.png"):
                        old_path = os.path.join(temp_dir, filename)
                        name_part = filename.rsplit(f"_{old_s_id}.png", 1)[0]
                        new_path = os.path.join(temp_dir, f"{name_part}_{new_s_id}.png")
                        try:
                            os.rename(old_path, new_path)
                        except FileExistsError:
                            os.replace(old_path, new_path)

            self._refresh_list(self.character_buttons, self.chars_from_series, self.char_scroll_frame)
            self.series_frame.pack_forget()
            self.warn_lbl.configure(text="")



    def _confirm_multiple_chars(self, char1, char2):
        self._clear_ch1()
        self._clear_ch2()
        self._confirm_char_choice(char1)
        self._confirm_char_choice(char2)

    def _clear_ch1(self):
        self.fst_textbox.delete(0.0, "end")
        if self.first_ch:
            self.chars_from_series.append(self.first_ch)
            self.first_ch=None
        self.chars_from_series.sort(key=lambda d: d.C_ID)
        self._refresh_list(self.character_buttons, self.chars_from_series, self.char_scroll_frame)
        self._reload_images()
    def _clear_ch2(self):
        self.snd_textbox.delete(0.0, "end")
        if self.second_ch:
            self.chars_from_series.append(self.second_ch)
            self.second_ch=None
        self.chars_from_series.sort(key=lambda d: d.C_ID)
        self._refresh_list(self.character_buttons, self.chars_from_series, self.char_scroll_frame)
        self._reload_images()

    def _display_image(self, char, target_img):
        if char:
            img_path=os.path.join(os.getcwd(), "temp", f"{char.name} - {char.S_ID}.png")
            try:
                pil_img=PILImage.open(img_path)
            except FileNotFoundError:
                pil_img = PILImage.new("RGB", (100, 200), color="gray")
            img=customtkinter.CTkImage(light_image=pil_img, dark_image=pil_img, size=(200,300))
            target_img.configure(image=img)
        else:
            target_img.configure(image=None)

    def _start_background_worker(self):
        def worker():
            while self.winfo_exists():
                with flask_app.app_context():
                    pending_ids=[c.C_ID for c in self._fetch_from_db()]

                for c_id in pending_ids:
                    with flask_app.app_context():
                        base_char=db.session.query(Character)\
                        .options(joinedload(Character.aliases))\
                        .options(joinedload(Character.series))\
                        .get(c_id)

                        if not base_char or base_char.is_valid!=0:
                            continue

                        companions=db.session.query(Character)\
                        .options(joinedload(Character.series))\
                        .filter(Character.S_ID==base_char.S_ID).all()

                        _=base_char.series.title
                        for alias in base_char.aliases: _=alias.alias
                        for char in companions: _=char.series.title

                        db.session.expunge_all()
                    self._download_images(base_char)
                    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                        executor.map(self._download_images, companions)
                    self.char_queue.put({
                        "original_character": base_char,
                        "companions": companions
                    })
        threading.Thread(target=worker, daemon=True).start()

    def _search_for_suggestions(self):
        self.match_suggestions.clear()
        data=self.chars_from_series.copy()
        data.append(self.first_ch)
        for idx1 in range(len(data)-1):
            for idx2 in range(idx1+1, len(data)):
                ch1=data[idx1]
                ch2=data[idx2]
                name1=ch1.name
                name2=ch2.name
                score=fuzz.token_set_ratio(name1, name2)
                if score>70:
                    key=f"score: {score}, {name1} - {name2}"
                    self.match_suggestions[key]=(ch1, ch2)

    def _search_for_series(self):
        series_title=self.first_ch.series.title
        res=set()
        for word in series_title.split():
            with flask_app.app_context():
                query=db.session.query(Series).filter(and_(Series.title.ilike(f"%{word}%"), Series.title.not_like(f"{series_title}"))).all()
            res = res | set(query)
        self.series_list=res


    def _load_new_character(self):
        if not hasattr(self, "_worker_running"):
            self._worker_running = True
            self._start_background_worker()
        try:
            data=self.char_queue.get_nowait()
        except queue.Empty:
            self.fst_textbox.delete(0.0, "end")
            self.fst_textbox.insert("0.0", "Loading, please wait...")
            self.after(200, self._load_new_character)
            return

        self.original_character=data['original_character']
        self.first_ch=self.original_character

        self.chars_from_series=[c for c in data['companions'] if c.C_ID!=self.original_character.C_ID]

        self.warn_lbl.configure(text="")
        self.series_frame.pack_forget()
        self.series_list=None
        self.warn_lbl.configure(text=f"Here are some similiar seires to\n{self.first_ch.series.title}")
        self.series_frame.pack(side="top")
        self._search_for_series()
        if self.series_list:
            self._refresh_list(self.series_buttons, self.series_list, self.series_frame)


        self._refresh_list(self.character_buttons, self.chars_from_series, self.char_scroll_frame)
        self.second_ch=None

        self.fst_textbox.delete(0.0, "end")
        self.snd_textbox.delete(0.0, "end")

        self.org_ch_label.configure(text=f"Original Character:\n{self.original_character.C_ID} - {self.original_character.name}\nAlso Known As:")
        self._refresh_list(self.alias_buttons, self.original_character.aliases, self.alias_frame)
        self.series_search_var.set("")

        self.fst_textbox.insert("0.0", self.original_character.name)
        self._reload_images()


    def _reload_images(self):
        self._display_image(self.first_ch, self.fst_img)
        self._display_image(self.second_ch, self.snd_img)


    def _create_alias(self):
        if self.original_character.C_ID==self.second_ch.C_ID:
            self.original_character=self.first_ch
            self.org_ch_label.configure(text=f"Original Character:\n{self.original_character.C_ID} - {self.original_character.name}\nAlso Known As:")
        with flask_app.app_context():
            alias=CharacterAlias(C_ID=self.first_ch.C_ID, alias=self.second_ch.name)
            try:
                db.session.add(alias)
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
        self._refresh_list(self.alias_buttons, self.original_character.aliases, self.alias_frame)

    def _merge_callback(self):
        if not self.second_ch or not self.first_ch:
            return
        alias_popup=CTkMessagebox(title="Save Alias??", message="Should ch2 be saved as an Alias of ch1??", icon="question", option_1="No", option_2="Yes")
        response=alias_popup.get()
        if response=="Yes":
            self._create_alias()

        with flask_app.app_context():
            query=text("CALL reassign_by_c_id(:old, :new)")
            db.session.execute(query, {
                "old": self.second_ch.C_ID,
                "new": self.first_ch.C_ID
            })
            db.session.commit()
        self.second_ch=None
        self._clear_ch2()
        self._refresh_list(self.character_buttons, self.chars_from_series, self.char_scroll_frame)
        self._search_for_suggestions()
        self._refresh_list(self.suggestion_buttons, self.match_suggestions, self.suggestions_frame)


    def _next_callback(self):
        with flask_app.app_context():
            char=db.session.query(Character).filter_by(C_ID=self.original_character.C_ID).first()
            if char:
                char.is_valid=True
                db.session.commit()

        self._load_new_character()
        self._search_for_suggestions()
        self._refresh_list(self.suggestion_buttons, self.match_suggestions, self.suggestions_frame)

    def _on_search_change(self):
        if self.search_timer is not None:
            self.after_cancel(self.search_timer)
        self.search_timer=self.after(300, lambda: self._execute_search())

    def _execute_search(self):
        phrase = self.series_search_var.get().lower()
        filtered = self._fetch_series(phrase)
        self._refresh_list(self.move_list, filtered, self.move_series_frame)

    def __init__(self, main_window):
        super().__init__()
        self.char_queue=queue.Queue(maxsize=10)

        self.main_window=main_window

        customtkinter.set_appearance_mode("dark")
        self.title("Character Validation")
        self.state('zoomed')
        width = self.winfo_screenwidth()
        height = self.winfo_screenheight()
        self.geometry("%dx%d" % (width, height))

        self.ch_list = None
        self.original_character=None
        self.first_ch=None
        self.second_ch=None
        self.chars_from_series=None
        self._search_timer = None
        self.character_buttons=[]
        self.alias_buttons=[]
        self.suggestion_buttons=[]
        self.match_suggestions={}
        self.series_buttons=[]
        self.series_list=[]
        self.move_list=[]

        self.search_timer=None

        main_frame=customtkinter.CTkFrame(self)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        main_frame.columnconfigure(0, weight=5)
        main_frame.columnconfigure(1, weight=7)
        main_frame.rowconfigure(0, weight=4)
        main_frame.rowconfigure(1, weight=1)

        self.left_frame=customtkinter.CTkFrame(main_frame)
        self.left_frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)

        l_content_frame=customtkinter.CTkFrame(self.left_frame, width=500, height=1000)
        l_content_frame.pack(anchor="nw", padx=20, pady=20)
        l_content_frame.pack_propagate(False)

        self.org_ch_label = customtkinter.CTkLabel(l_content_frame)
        self.org_ch_label.pack(side="top", padx=5, pady=5)

        self.alias_frame = customtkinter.CTkScrollableFrame(l_content_frame, width=200, height=200)
        self.alias_frame.pack(side="top", padx=5, pady=5)




        self.series_search_var = customtkinter.StringVar()
        self.series_search_var.trace_add("write", lambda *args: self._on_search_change())

        self.series_entry = customtkinter.CTkEntry(l_content_frame, textvariable=self.series_search_var,
                                                   placeholder_text="Search series")
        self.series_entry.pack(fill="x", padx=5, pady=5)
        self.move_series_frame=customtkinter.CTkScrollableFrame(l_content_frame, width=200, height=200)
        self.move_series_frame.pack(fill="x", padx=5, pady=5)

        self.warn_lbl = customtkinter.CTkLabel(l_content_frame, text="")
        self.warn_lbl.pack(side="top", padx=5, pady=5)
        self.series_frame=customtkinter.CTkScrollableFrame(l_content_frame, width=200, height=200)
        self.series_frame.pack(side="top", padx=5, pady=5)





        right_frame=customtkinter.CTkFrame(main_frame)
        right_frame.grid(row=0, column=1, sticky="nse", padx=20, pady=20)

        right_frame.columnconfigure(0, weight=8)
        right_frame.columnconfigure(1, weight=3)

        textbox_frame=customtkinter.CTkFrame(right_frame, width=700, height=500)
        textbox_frame.grid(row=0, column=0, padx=5, pady=20)
        textbox_frame.grid_propagate(False)

        self.fst_img=customtkinter.CTkLabel(textbox_frame, text="")
        self.fst_img.grid(row=0, column=0, padx=5, pady=5)

        self.snd_img=customtkinter.CTkLabel(textbox_frame, text="")
        self.snd_img.grid(row=0, column=1, padx=5, pady=5)

        fst_label=customtkinter.CTkLabel(textbox_frame, text="First Character")
        fst_label.grid(row=1, column=0, padx=5, pady=5)

        self.fst_textbox=customtkinter.CTkTextbox(textbox_frame, height=40)
        self.fst_textbox.grid(row=2, column=0, padx=5, pady=5)

        clear_ch1=customtkinter.CTkButton(textbox_frame, text="Clear ch1", command=self._clear_ch1)
        clear_ch1.grid(row=3, column=0, padx=5, pady=5)

        snd_label = customtkinter.CTkLabel(textbox_frame, text="Second Character")
        snd_label.grid(row=1, column=1, padx=5, pady=5)

        self.snd_textbox = customtkinter.CTkTextbox(textbox_frame, height=40)
        self.snd_textbox.grid(row=2, column=1, padx=5, pady=5)

        clear_ch2 = customtkinter.CTkButton(textbox_frame, text="Clear ch2", command=self._clear_ch2)
        clear_ch2.grid(row=3, column=1, padx=5, pady=5)

        merge_button=customtkinter.CTkButton(textbox_frame, text="Merge", fg_color="green", command=self._merge_callback)
        merge_button.grid(row=4, column=0, padx=5, pady=5)

        next_button=customtkinter.CTkButton(textbox_frame, text="Next", fg_color="yellow", command=self._next_callback)
        next_button.grid(row=4, column=1, padx=5, pady=5)

        search_frame=customtkinter.CTkFrame(right_frame)
        search_frame.grid(row=0, column=1, padx=5, pady=20)

        search_lbl = customtkinter.CTkLabel(search_frame, text="Search Existing Records")
        search_lbl.pack(side="top", pady=(10, 5))

        self.char_scroll_frame = customtkinter.CTkScrollableFrame(search_frame, height=300, width=300)
        self.char_scroll_frame.pack(padx=10, pady=(0, 10))


        suggestions_lbl=customtkinter.CTkLabel(search_frame, text="Suggestions")
        suggestions_lbl.pack(side="top", pady=(10, 5))
        self.suggestions_frame=customtkinter.CTkScrollableFrame(search_frame, height=300, width=300)
        self.suggestions_frame.pack(padx=10, pady=(0, 10))

        self._load_new_character()

        
        # if not self.chars_from_series:










app=CharacterApp(None)
app.mainloop()