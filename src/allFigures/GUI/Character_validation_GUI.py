import customtkinter
from sqlalchemy import and_, column, true, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload
from CTkMessagebox import CTkMessagebox
from run import app as flask_app
from models.models import db, Figure, Character, CharacterAlias, Series


class CharacterApp(customtkinter.CTk):
    def _fetch_from_db(self):
        with flask_app.app_context():
            query=db.session.query(Character)\
                .options(joinedload(Character.aliases))\
                .filter(Character.is_valid==0)\
                .order_by(Character.S_ID.asc())\
                .all()
            return query


    def _fetch_characters_from_series(self):
        with flask_app.app_context():

            query=db.session.query(Character).filter(and_(
                         Character.S_ID == self.original_character.S_ID,
                (Character.C_ID!=self.first_ch.C_ID) if self.first_ch else true(),
                        (Character.C_ID!=self.second_ch.C_ID) if self.second_ch else true())).all()
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


        return

    def _refresh_list(self, button_list, dataset, target_frame):
        for btn in button_list:
            btn.destroy()
        button_list.clear()

        for ch in dataset:
            btn=customtkinter.CTkButton(
                target_frame,
                text=(f"{ch.C_ID} - {ch.name}") if target_frame==self.char_scroll_frame else f"{ch.CA_ID} - {ch.alias}",
                anchor="w",
                fg_color="transparent",
                text_color=("black", "white"),
                hover_color=("gray70", "gray30"),
                command=(lambda v=ch: self._confirm_char_choice(v)) if target_frame==self.char_scroll_frame else None,
            )
            btn.pack(fill="x", pady=1)
            button_list.append(btn)

    def _clear_ch1(self):
        self.fst_textbox.delete(0.0, "end")
        if self.first_ch:
            self.chars_from_series.append(self.first_ch)
            self.first_ch=None
        self.chars_from_series.sort(key=lambda d: d.C_ID)
        self._refresh_list(self.character_buttons, self.chars_from_series, self.char_scroll_frame)

    def _clear_ch2(self):
        self.snd_textbox.delete(0.0, "end")
        if self.second_ch:
            self.chars_from_series.append(self.second_ch)
            self.second_ch=None
        self.chars_from_series.sort(key=lambda d: d.C_ID)
        self._refresh_list(self.character_buttons, self.chars_from_series, self.char_scroll_frame)


    def _load_new_character(self):
        self.ch_list=self._fetch_from_db()
        self.original_character=self.ch_list.pop(0)
        self.first_ch=self.original_character
        self.chars_from_series=self._fetch_characters_from_series()
        self._refresh_list(self.character_buttons, self.chars_from_series, self.char_scroll_frame)

        self.fst_textbox.delete(0.0, "end")
        self.snd_textbox.delete(0.0, "end")

        self.org_ch_label.configure(text=f"Original Character:\n{self.original_character.C_ID} - {self.original_character.name}\nAlso Known As:")
        self._refresh_list(self.alias_buttons, self.original_character.aliases, self.alias_frame)


        self.fst_textbox.insert("0.0", self.original_character.name)

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



    def __init__(self, main_window):
        super().__init__()
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

        main_frame=customtkinter.CTkFrame(self)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        main_frame.columnconfigure(0, weight=5)
        main_frame.columnconfigure(1, weight=7)
        main_frame.rowconfigure(0, weight=4)
        main_frame.rowconfigure(1, weight=1)

        left_frame=customtkinter.CTkFrame(main_frame)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)

        l_content_frame=customtkinter.CTkFrame(left_frame, width=500)
        l_content_frame.pack(anchor="nw", padx=20, pady=20)
        l_content_frame.pack_propagate(False)

        self.org_ch_label=customtkinter.CTkLabel(l_content_frame)
        self.org_ch_label.pack(side="top", padx=5, pady=5)

        self.alias_frame = customtkinter.CTkScrollableFrame(l_content_frame, width=200, height=50)
        self.alias_frame.pack(side="top", padx=5, pady=5)



        right_frame=customtkinter.CTkFrame(main_frame)
        right_frame.grid(row=0, column=1, sticky="nse", padx=20, pady=20)

        right_frame.columnconfigure(0, weight=8)
        right_frame.columnconfigure(1, weight=3)

        textbox_frame=customtkinter.CTkFrame(right_frame, width=700, height=350)
        textbox_frame.grid(row=0, column=0, padx=5, pady=20)
        textbox_frame.grid_propagate(False)

        fst_label=customtkinter.CTkLabel(textbox_frame, text="First Character")
        fst_label.grid(row=0, column=0, padx=5, pady=5)

        self.fst_textbox=customtkinter.CTkTextbox(textbox_frame, height=40)
        self.fst_textbox.grid(row=1, column=0, padx=5, pady=5)

        clear_ch1=customtkinter.CTkButton(textbox_frame, text="Clear ch1", command=self._clear_ch1)
        clear_ch1.grid(row=2, column=0, padx=5, pady=5)

        snd_label = customtkinter.CTkLabel(textbox_frame, text="Second Character")
        snd_label.grid(row=0, column=1, padx=5, pady=5)

        self.snd_textbox = customtkinter.CTkTextbox(textbox_frame, height=40)
        self.snd_textbox.grid(row=1, column=1, padx=5, pady=5)

        clear_ch2 = customtkinter.CTkButton(textbox_frame, text="Clear ch2", command=self._clear_ch2)
        clear_ch2.grid(row=2, column=1, padx=5, pady=5)

        merge_button=customtkinter.CTkButton(textbox_frame, text="Merge", fg_color="green", command=self._merge_callback)
        merge_button.grid(row=3, columnspan=2, padx=5, pady=5)

        search_frame=customtkinter.CTkFrame(right_frame)
        search_frame.grid(row=0, column=1, padx=5, pady=20)

        search_lbl = customtkinter.CTkLabel(search_frame, text="Search Existing Records")
        search_lbl.pack(side="top", pady=(10, 5))

        self.char_scroll_frame = customtkinter.CTkScrollableFrame(search_frame, height=300, width=300)
        self.char_scroll_frame.pack(padx=10, pady=(0, 10))
        self._load_new_character()









app=CharacterApp(None)
app.mainloop()