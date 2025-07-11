from kivymd.app import MDApp
from kivymd.uix.button import MDFlatButton
from kivymd.uix.screen import MDScreen

class TestApp(MDApp):
    def build(self):
        return MDScreen(
            MDFlatButton(
                text="Teste",
                pos_hint={"center_x": 0.5, "center_y": 0.5},
                on_release=lambda x: print("Botão carregado!")
            )
        )

TestApp().run()
