import re
import os
import queue
import requests
import threading
import webbrowser
import urllib.parse
import customtkinter

from PIL import Image
from io import BytesIO
from CTkListbox import CTkListbox
from customtkinter import CTkImage
from backend.run import app as flask_app
from sqlalchemy.exc import IntegrityError
from services.code_extractor import clean_for_fuzz
from static.datasets.domain_noise import DOMAIN_NOISE
from code_extractor import get_links, get_data, match
from services.scrapers.scraper_functions import process_offer_images
from app.models import db, Figure, Character, Series, Image as model_Image, Offer, StoreEnum

# ext = external source

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Referer": "https://myfigurecollection.net/"
}

current_file_path = os.path.abspath(__file__)
services_dir = os.path.dirname(current_file_path)
app_dir = os.path.dirname(services_dir)

class ComparatorApp(customtkinter.CTk):

    def open_url(self, url):
        webbrowser.open_new(url)

    def fetch_data_from_db(self):
        with flask_app.app_context():
            query=db.session.query(Figure.F_ID,
                             Figure.name.label("fig_name"),
                             Character.name.label("char_name"),
                             Series.title.label("series"),
                             Figure.manufacturer,
                             Figure.code,
                             Offer.O_ID
                             ).select_from(Figure)\
                .join(Character, Character.C_ID == Figure.C_ID)\
                .join(Series, Series.S_ID == Character.S_ID)\
                .join(Offer, Offer.F_ID == Figure.F_ID)\
                .filter(Figure.code.is_(None))
            if self.queued_f_ids:
                query=query.filter(Figure.F_ID.notin_(self.queued_f_ids))
            row=query.order_by(Offer.O_ID).first()
            if not row:
                return None
            self.queued_f_ids.add(row.F_ID)
            images_data=db.session.query(model_Image.path).filter_by(O_ID=row.O_ID).all()
            images={img[0] for img in images_data}
            result={
                "F_ID":row.F_ID,
                "fig_name":row.fig_name,
                "char_name":row.char_name,
                "series":row.series,
                "manufacturer":row.manufacturer,
                "code":row.code,
                "images":images,
            }
            print(result)
            return result





    def fetch_data_from_ext(self, fig_db):
        char_name=fig_db["char_name"]
        manufacturer=fig_db.get("manufacturer", " ")
        fig_name=fig_db.get("fig_name")
        noise=DOMAIN_NOISE | set(char_name.lower().split() + manufacturer.lower().split())
        clean_fig_name=re.sub(r'[^a-zA-Z0-9\s]', ' ', fig_name.lower())
        meaningful_words=[word for word in clean_fig_name.split() if word not in noise]
        depiction=" ".join(meaningful_words[-5:])
        search1 = f"site:myfigurecollection.net item {char_name} {manufacturer} {depiction}"
        search2 = f"site:dystryktzero.pl {fig_name}"
        links1=get_links(search1)
        links2=get_links(search2)
        all_links=links2+links1
        if not links1 and not links2:
            print(f"No figures for {fig_name}")
            return None

        first_link=all_links[0]
        pending_links=all_links[1:]


        data=get_data([first_link])
        target_fuzz=clean_for_fuzz(fig_name)
        data=match(data, target_fuzz)
        return {
            "data":data,
            "pending_links":pending_links,
            "target_fuzz":target_fuzz,
        }







    def update_code(self):
        with flask_app.app_context():
            query = db.session.query(Figure).filter(Figure.F_ID==self.db_F_ID).first()
            if query:
                try:
                    query.code=self.ext_code
                    db.session.commit()
                    return True
                except IntegrityError:
                    db.session.rollback()
                    self.error_label.configure(text="Error! Code already exists in database", text_color="red")
                    return False
            return False

    def add_dystrykt_offer(self):
        with flask_app.app_context():
            link=self.ext_link
            curr_fig=self.figures_from_ext[self.main_fig_k]
            self.error_label.configure(text="")
            if "dystryktzero" in link:
                try:
                    F_ID=self.db_F_ID
                    store=StoreEnum.DYSTRYKTZERO
                    price=curr_fig.get("price")
                    status=curr_fig.get("status")
                    images=curr_fig.get("image")

                    offer=Offer(F_ID=F_ID,link=link, store=store,price=price,status=status)
                    db.session.add(offer)
                    db.session.flush()
                    process_offer_images(offer.O_ID, images)
                    db.session.commit()
                except IntegrityError:
                    db.session.rollback()
                    self.error_label.configure(text="Error! Code already exists in database", text_color="red")
                    return


    def confirm_callback(self):
        if not self.ext_code:
            self.error_label.configure(text="Error! Code is empty, please scrape manually", text_color="red")
            return

        self.error_label.configure(text="")
        if not self.update_code():
            return

        print("Connection saved in the db")

        self.add_dystrykt_offer()
        self.load_next_figure_to_gui()



    def reject_callback(self):
        self.error_label.configure(text="")
        try:
            self.data_queue.get_nowait()
        except queue.Empty:
            print("Queue is empty")
            self.error_label.configure(text="Error! Queue is empty", text_color="red")
        self.load_next_figure_to_gui()


    def prev_img_callback(self):
        if not self.image_list:
            return
        self.image_list=self.image_list[-1:]+self.image_list[:-1]

        new_path=os.path.join(app_dir, "static", self.image_list[0])
        new_pil_image=Image.open(new_path)
        new_ctk_image=customtkinter.CTkImage(new_pil_image, size=(200,300))
        self.image_db_label.configure(image=new_ctk_image)


    def next_img_callback(self):
        if not self.image_list:
            return
        self.image_list = self.image_list[1:] + self.image_list[:1]

        new_path = os.path.normpath(os.path.join(app_dir, "static", self.image_list[0]))
        new_pil_image = Image.open(new_path)
        new_ctk_image = customtkinter.CTkImage(new_pil_image, size=(200, 300))
        self.image_db_label.configure(image=new_ctk_image)

    def load_button_callback(self):
        selected=self.ext_listbox.get()
        if not selected:
            return
        new_key=selected.split(":", 1)[1].strip()
        if self.main_fig_k==new_key:
            return
        self.main_fig_k=new_key
        ext_fig=self.figures_from_ext[new_key]
        self.ext_fig_name.configure(text=f"Name: {new_key}")

        self.ext_series=ext_fig.get("series")
        self.ext_fig_series.configure(text=f"Series: {self.ext_series}")

        self.ext_score=ext_fig.get("score")
        self.ext_fig_score.configure(text=f"Score: {self.ext_score}", text_color="green" if self.ext_score>85 else "red")

        self.ext_code = ext_fig.get("code", "")
        self.ext_fig_code.configure(text=f"Code: {self.ext_code}")

        self.ext_link = ext_fig.get("figure_link", "")
        self.ext_fig_link.configure(text=f"Link: {self.ext_link}", text_color="blue", cursor="hand2")
        self.ext_fig_link.unbind("<Button-1>")
        self.ext_fig_link.bind("<Button-1>", lambda event: self.open_url(self.ext_link))

        try:
            resp = requests.get(ext_fig["image"][0], headers=headers, stream=True, timeout=30)
            if resp.ok:
                pil_ext_new_img = Image.open(BytesIO(resp.content))
            else:
                pil_ext_new_img = Image.new("RGB", (200, 300), color="gray")
        except Exception:
            pil_ext_new_img = Image.new("RGB", (200, 300), color="gray")

        ctk_ext_new_img = CTkImage(light_image=pil_ext_new_img, dark_image=pil_ext_new_img, size=(200, 300))
        self.image_ext_label.configure(image=ctk_ext_new_img)


    def confirm_manual_callback(self):
        manual_code=self.db_enter_code_textbox.get("0.0", "end").strip()
        if not manual_code:
            return
        self.ext_code=manual_code
        if self.update_code():
            self.load_next_figure_to_gui()
            self.db_enter_code_textbox.delete("0.0", "end")

    def load_next_figure_to_gui(self):
        self.loading_frame.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.loading_frame.lift()
        self.after(100, self.check_queue)

    def worker_get_data(self):
        while True:
            fig_db=self.fetch_data_from_db()
            if not fig_db:
                self.data_queue.put({"db": None, "ext": None})
                return
            fig_ext=self.fetch_data_from_ext(fig_db)
            if not fig_ext:
                print("Error fetching figures from ext")
            self.data_queue.put({"db": fig_db, "ext": fig_ext})


    def check_queue(self):
        try:
            data=self.data_queue.get_nowait()

            self.update_gui_with_new_data(data)
            self.loading_frame.place_forget()
        except queue.Empty:
            self.after(100, self.check_queue)
        except Exception as e:
            print(f"Critical GUI error: {e}")
            self.loading_frame.place_forget()

    def raise_finish(self):
        print("All figures checked!")
        finish_frame = customtkinter.CTkFrame(self, fg_color="green", corner_radius=0)
        finish_label = customtkinter.CTkLabel(finish_frame, text="Finished checking figures")
        finish_label.pack(expand=True)
        finish_frame.place(relx=0, rely=0, relwidth=1, relheight=1)
        finish_frame.lift()

    def load_more_button_callback(self):
        if not self.pending_links:
            return

        self.ext_load_more_button.configure(state="disabled", text="Loading...")
        threading.Thread(target=self.worker_load_more, daemon=True).start()

    def worker_load_more(self):
        new_link=self.pending_links.pop(0)
        new_data=get_data([new_link])

        new_data=match(new_data, self.target_fuzz)
        self.after(0, self.append_new_ext_data, new_data)

    def append_new_ext_data(self, new_data):
        self.figures_from_ext.update(new_data)

        try:
            self.ext_listbox.delete("all")
        except:
            pass

        sorted_ext_items=sorted(
            self.figures_from_ext.items(),
            key=lambda x: x[1].get("score", 0),
            reverse=True,
        )

        for key, value in sorted_ext_items:
            self.ext_listbox.insert("end", f"{value.get("score", 0)}: {key}")

        remaining=len(self.pending_links)
        if remaining>0:
            self.ext_load_more_button.configure(state="normal", text=f"Load more (+{remaining})")
        else:
            self.ext_load_more_button.configure(state="disabled", text="No more figures")

    def update_gui_with_new_data(self, data):
        self.error_label.configure(text="")
        ext_payload=data.get("ext")
        if ext_payload:
            self.figures_from_ext=ext_payload["data"]
            self.pending_links=ext_payload.get("pending_links")
            self.target_fuzz=ext_payload.get("target_fuzz")

            remaining=len(self.pending_links)
            if remaining>0:
                self.ext_load_more_button.configure(state="normal", text=f"Load more (+{remaining})")
            else:
                self.ext_load_more_button.configure(state="disabled", text="No more figures")
        else:
            self.figures_from_ext={}
            self.pending_links=[]
        figure_db=data.get("db")
        if not figure_db:
            self.raise_finish()
            return


        self.db_name=figure_db.get("fig_name")
        self.db_series=figure_db.get("series")
        self.db_F_ID=figure_db.get('F_ID')
        self.db_manuf=figure_db.get('manufacturer')
        self.db_fig_name.configure(text=f"Name: {self.db_name}")
        self.db_fig_name.unbind("<Button-1>")
        label_text=self.db_fig_name.cget("text").split(":", 1)[1]
        safe_label_text = urllib.parse.quote_plus(label_text)
        search=f"https://www.google.com/search?client=opera-gx&q={safe_label_text}+JAN"
        self.db_fig_name.bind("<Button-1>", lambda event: self.open_url(search))
        self.db_fig_series.configure(text=f"Series: {self.db_series}")
        self.db_fig_F_ID.configure(text=f"Figure ID: {self.db_F_ID}")
        self.db_fig_manuf.configure(text=f"Manufacturer: {self.db_manuf}")

        self.image_list = list((figure_db.get("images", [])))
        self.image_list.sort()

        if self.image_list:
            main_image = self.image_list[0]
            full_path = os.path.normpath(os.path.join(app_dir, "static", main_image))
            try:
                pil_db_image=Image.open(full_path)
            except FileNotFoundError:
                pil_db_image = Image.new("RGB", (200, 300), color="gray")
        else:
            pil_db_image = Image.new("RGB", (200, 300), color="gray")
        ctk_db_img=customtkinter.CTkImage(light_image=pil_db_image, dark_image=pil_db_image, size=(200,300))
        self.image_db_label.configure(image=ctk_db_img)

        sorted_ext_items=sorted(
            self.figures_from_ext.items(),
            key=lambda x: x[1].get("score", 0),
            reverse=True,
        )

        if sorted_ext_items:
            self.main_fig_k=sorted_ext_items[0][0]
            ext_fig=sorted_ext_items[0][1]

            self.ext_series = ext_fig.get('series', " ")
            self.ext_score = ext_fig.get("score", 0)
            self.ext_link = ext_fig.get("figure_link", "")
            self.ext_code = ext_fig.get("code", "")

            self.ext_fig_name.configure(text=f"Name: {self.main_fig_k}")
            self.ext_fig_series.configure(text=f"Series: {self.ext_series}")
            self.ext_fig_score.configure(text=f"Score: {self.ext_score}", text_color="green" if self.ext_score > 85 else "red")
            self.ext_fig_link.configure(text=f"Link: {self.ext_link}", text_color="blue", cursor="hand2")
            self.ext_fig_link.unbind("<Button-1>")
            self.ext_fig_link.bind("<Button-1>", lambda event: self.open_url(self.ext_link))
            self.ext_fig_code.configure(text=f"Code: {self.ext_code}", text_color="red" if not self.ext_code else "white")
        else:
            self.main_fig_k = None
            self.ext_code = None
            self.ext_link = ""

            self.ext_fig_name.configure(text="Name: No Results (Use Load More)")
            self.ext_fig_series.configure(text="Series: ")
            self.ext_fig_score.configure(text="Score: ")
            self.ext_fig_code.configure(text="Code: ")
            self.ext_fig_link.configure(text="Link: ", cursor="arrow")
            self.ext_fig_link.unbind("<Button-1>")

            try:
                self.ext_listbox.delete("all")
            except:
                pass

            pil_blank = Image.new("RGB", (200, 300), color="gray")
            ctk_blank = CTkImage(light_image=pil_blank, dark_image=pil_blank, size=(200, 300))
            self.image_ext_label.configure(image=ctk_blank)
            return


        try:
            resp=requests.get(ext_fig["image"][0], headers=headers, stream=True, timeout=30)
            if resp.ok:
                pil_ext_img=Image.open(BytesIO(resp.content))
            else:
                pil_ext_img = Image.new("RGB", (200, 300), color="gray")
        except Exception:
            pil_ext_img = Image.new("RGB", (200, 300), color="gray")

        ctk_ext_img=CTkImage(light_image=pil_ext_img, dark_image=pil_ext_img, size=(200,300))
        self.image_ext_label.configure(image=ctk_ext_img)

        try:
            self.ext_listbox.delete("all")
        except:
            pass

        for key, value in sorted_ext_items:
            self.ext_listbox.insert("end", f"{value.get('score', 0)}: {key}")


    def __init__(self):
        super().__init__()

        self.queued_f_ids=set()
        self.pending_links=None
        self.target_fuzz=None

        self.data_queue=queue.Queue()
        self.loading_frame=customtkinter.CTkFrame(self, fg_color="gray", corner_radius=0)
        self.loading_label=customtkinter.CTkLabel(
            self.loading_frame,
            text="Loading data..."
        )
        self.loading_label.pack(expand=True)



        customtkinter.set_appearance_mode("dark")
        self.title("ext code comparator")
        self.state('zoomed')
        width = self.winfo_screenwidth()
        height = self.winfo_screenheight()
        self.geometry("%dx%d" % (width, height))



        main_frame = customtkinter.CTkFrame(self)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        main_frame.grid_columnconfigure(0, weight=1, uniform="a")
        main_frame.grid_columnconfigure(1, weight=1, uniform="a")

        main_frame.grid_rowconfigure(0, weight=1)
        main_frame.grid_rowconfigure(1, weight=0)

        self.db_frame=customtkinter.CTkFrame(main_frame)
        self.ext_frame=customtkinter.CTkFrame(main_frame)
        self.bottom_frame=customtkinter.CTkFrame(main_frame)
        self.button_frame=customtkinter.CTkFrame(self.bottom_frame)

        # left panel - db_frame
        self.db_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

        db_info_frame=customtkinter.CTkFrame(self.db_frame, fg_color="transparent")
        db_info_frame.pack(side="top", fill="x", padx=20, pady=10)

        self.db_name=None
        self.db_fig_name=customtkinter.CTkLabel(db_info_frame, wraplength=450, justify="left")
        self.db_fig_name.pack(anchor="w")

        self.db_series=None
        self.db_fig_series=customtkinter.CTkLabel(db_info_frame)
        self.db_fig_series.pack(anchor="w")

        self.db_F_ID=None
        self.db_fig_F_ID=customtkinter.CTkLabel(db_info_frame)
        self.db_fig_F_ID.pack(anchor="w")

        self.db_manuf=None
        self.db_fig_manuf=customtkinter.CTkLabel(db_info_frame)
        self.db_fig_manuf.pack(anchor="w")

        self.image_list=[]
        self.image_db_label=customtkinter.CTkLabel(self.db_frame, text="")
        self.image_db_label.pack(side="top", pady=10)

        self.db_buttons_frame = customtkinter.CTkFrame(self.db_frame)
        self.db_buttons_frame.pack(side="top", pady=5)

        prev_button = customtkinter.CTkButton(self.db_buttons_frame, text="<<", command=self.prev_img_callback)
        prev_button.grid(row=0, column=0, padx=10, pady=10, sticky="e")

        next_button = customtkinter.CTkButton(self.db_buttons_frame, text=">>", command=self.next_img_callback)
        next_button.grid(row=0, column=1, padx=10, pady=10, sticky="w")

        manual_code_frame=customtkinter.CTkFrame(self.db_frame, fg_color="transparent")
        manual_code_frame.pack(side="top", padx=5, pady=5)

        self.db_enter_code_textbox=customtkinter.CTkTextbox(manual_code_frame, height=30)
        self.db_enter_code_textbox.pack(side="left", pady=10, padx=10)

        self.db_confirm_manual_button=customtkinter.CTkButton(manual_code_frame, text="confirm", command=self.confirm_manual_callback)
        self.db_confirm_manual_button.pack(side="right", pady=10, padx=10)




















        self.figures_from_ext={}
        self.main_fig_k=None

        self.ext_frame.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")

        ext_info_frame=customtkinter.CTkFrame(self.ext_frame, fg_color="transparent")
        ext_info_frame.pack(side="top", fill="x", padx=20, pady=10)

        self.ext_fig_name=customtkinter.CTkLabel(ext_info_frame, wraplength=450, justify="left")
        self.ext_fig_name.pack(anchor="w")

        self.ext_series=None
        self.ext_fig_series=customtkinter.CTkLabel(ext_info_frame)
        self.ext_fig_series.pack(anchor="w")

        self.ext_score=None
        self.ext_fig_score=customtkinter.CTkLabel(ext_info_frame)
        self.ext_fig_score.pack(anchor="w")

        self.ext_code=None
        self.ext_fig_code=customtkinter.CTkLabel(ext_info_frame)
        self.ext_fig_code.pack(anchor="w")

        self.ext_link=None
        self.ext_fig_link=customtkinter.CTkLabel(ext_info_frame, wraplength=450, justify="left")
        self.ext_fig_link.pack(anchor="w")






        ext_controls_frame = customtkinter.CTkFrame(self.ext_frame, fg_color="transparent")
        ext_controls_frame.pack(side="bottom", fill="both", expand=True, padx=20, pady=(0, 20))

        self.ext_listbox = CTkListbox(ext_controls_frame)
        self.ext_listbox.pack(side="top", fill="both", expand=True, pady=(0, 10))

        ext_buttons_subframe = customtkinter.CTkFrame(ext_controls_frame, fg_color="transparent")
        ext_buttons_subframe.pack(side="bottom", fill="x")

        ext_load_button = customtkinter.CTkButton(ext_buttons_subframe, text="Load Selected", command=self.load_button_callback)
        ext_load_button.pack(side="left", expand=True, padx=5)

        self.ext_load_more_button = customtkinter.CTkButton(ext_buttons_subframe, command=self.load_more_button_callback)
        self.ext_load_more_button.pack(side="right", expand=True, padx=5)

        self.image_ext_label = customtkinter.CTkLabel(self.ext_frame, text="")
        self.image_ext_label.pack(side="top", pady=10)















        self.bottom_frame.grid(row=1, column=0, columnspan=2, padx=10, pady=10, sticky="ew")
        self.button_frame.pack(side="bottom")

        self.button_frame.grid_columnconfigure(0, weight=1)
        self.button_frame.grid_columnconfigure(1, weight=1)

        self.error_label = customtkinter.CTkLabel(self.bottom_frame)
        self.error_label.pack(pady=10, padx=10)


        self.confirm_button = customtkinter.CTkButton(self.button_frame, text="Confirm", command=self.confirm_callback, fg_color="green")
        self.confirm_button.grid(row=0, column=0, padx=20, pady=20, sticky="e")

        self.reject_button = customtkinter.CTkButton(self.button_frame, text="Reject", command=self.reject_callback, fg_color="red")
        self.reject_button.grid(row=0, column=1, padx=20, pady=20, sticky="w")

        threading.Thread(target=self.worker_get_data, daemon=True).start()

        self.load_next_figure_to_gui()

app=ComparatorApp()
app.mainloop()