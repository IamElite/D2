from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

class ButtonMaker:
    def __init__(self):
        self.__button = []
        self.__header_button = []
        self.__header2_button = []
        self.__first_body_button = []
        self.__last_body_button = []
        self.__footer_button = []

    def ubutton(self, key, link, position=None, style=None):
        try:
            btn = InlineKeyboardButton(text=key, url=link)
        except TypeError:
            btn = InlineKeyboardButton(text=key, url=link)
        if position == 'header2':
            self.__header2_button.append(btn)
            return
        if not position:
            self.__button.append(btn)
        elif position == 'header':
            self.__header_button.append(btn)
        elif position == 'f_body':
            self.__first_body_button.append(btn)
        elif position == 'l_body':
            self.__last_body_button.append(btn)
        elif position == 'footer':
            self.__footer_button.append(btn)

    def ibutton(self, key, data, position=None, style=None):
        try:
            btn = InlineKeyboardButton(text=key, callback_data=data)
        except TypeError:
            btn = InlineKeyboardButton(text=key, callback_data=data)
        if position == 'header2':
            self.__header2_button.append(btn)
            return
        if not position:
            self.__button.append(btn)
        elif position == 'header':
            self.__header_button.append(btn)
        elif position == 'f_body':
            self.__first_body_button.append(btn)
        elif position == 'l_body':
            self.__last_body_button.append(btn)
        elif position == 'footer':
            self.__footer_button.append(btn)

    def data_button(self, key, data, position=None, style=None):
        return self.ibutton(key, data, position, style)

    def url_button(self, key, link, position=None, style=None):
        return self.ubutton(key, link, position, style)

    def build_menu(self, b_cols=1, h_cols=8, fb_cols=2, lb_cols=2, f_cols=8):
        menu = [self.__button[i:i+b_cols] for i in range(0, len(self.__button), b_cols)]
        if self.__header_button:
            if len(self.__header_button) > h_cols:
                header_buttons = [self.__header_button[i:i+h_cols] for i in range(0, len(self.__header_button), h_cols)]
                menu = header_buttons + menu
            else:
                menu.insert(0, self.__header_button)
        if self.__header2_button:
            menu.insert(1 if self.__header_button else 0, self.__header2_button)
        if self.__first_body_button:
            if len(self.__first_body_button) > fb_cols:
                [menu.append(self.__first_body_button[i:i+fb_cols]) for i in range(0, len(self.__first_body_button), fb_cols)]
            else:
                menu.append(self.__first_body_button)
        if self.__last_body_button:
            if len(self.__last_body_button) > lb_cols:
                [menu.append(self.__last_body_button[i:i+lb_cols]) for i in range(0, len(self.__last_body_button), lb_cols)]
            else:
                menu.append(self.__last_body_button)
        if self.__footer_button:
            if len(self.__footer_button) > f_cols:
                [menu.append(self.__footer_button[i:i+f_cols]) for i in range(0, len(self.__footer_button), f_cols)]
            else:
                menu.append(self.__footer_button)
        return InlineKeyboardMarkup(menu)
