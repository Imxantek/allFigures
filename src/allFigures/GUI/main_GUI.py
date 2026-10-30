import customtkinter
from Code_comparator_GUI import CodeApp
from Character_validation_GUI import CharacterApp

class Main(customtkinter.CTk):
    def _exit_button_callback(self):
        self.withdraw()
        self.after(100, self.quit)
    def _code_button_callback(self):
        self.withdraw()
        if self.code_comparator is None:
            self.code_comparator = CodeApp(self)
        else:
            self.code_comparator.deiconify()
    def _character_button_callback(self):
        self.withdraw()
        if self.character_comparator is None:
            self.character_comparator=CharacterApp(self)
        else:
            self.character_comparator.deiconify()
    def __init__(self):
        super().__init__()
        self.code_comparator=None
        self.character_comparator=None
        customtkinter.set_appearance_mode("dark")
        self.title("allFigures GUI")
        self.state('zoomed')
        width = 220
        height = 220
        self.geometry("%dx%d" % (width, height))
        main_frame = customtkinter.CTkFrame(self)
        main_frame.pack(fill="y", expand=True, padx=5, pady=5)
        content_frame = customtkinter.CTkFrame(main_frame, height=200, width=300)
        content_frame.pack(fill="both", expand=True, padx=20, pady=20)

        title_label = customtkinter.CTkLabel(content_frame, text="Main Menu")
        title_label.pack(side="top")

        character_validator_button=customtkinter.CTkButton(content_frame, text="Character Validator", command=self._character_button_callback)
        character_validator_button.pack(side="top", pady=5, padx=10)

        code_comparator_button=customtkinter.CTkButton(content_frame, text="Code Comparator", command=self._code_button_callback)
        code_comparator_button.pack(side="top", pady=5, padx=10)

        exit_button = customtkinter.CTkButton(content_frame, text="Exit", command=self._exit_button_callback)
        exit_button.pack(side="top", pady=5, padx=10)


app=Main()
app.mainloop()