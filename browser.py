import socket
import ssl
import time
import tkinter
import tkinter.font

CACHE = {}
FONTS = {}
MEASURES = {}

class RedirectLoopError(Exception):
    pass

class URL:
    def __init__(self, url):
        self.scheme, url = url.split("://", 1)
        assert self.scheme in ["http", "https", "file"]

        if self.scheme == "file":
            self.host = None
            self.port = None
            self.path = url
            return

        if "/" not in url:
            url = url + "/"
        self.host, url = url.split("/", 1)
        self.path = "/" + url

        if self.scheme == "http":
            self.port = 80
        elif self.scheme == "https":
            self.port = 443

        if ":" in self.host:
            self.host, port = self.host.split(":", 1)
            self.port = int(port)

    def __repr__(self):
        return f"URL(scheme={self.scheme}, host={self.host}, port={self.port}, path={repr(self.path)})"

    def request(self, headers=None):
        if self.scheme == "file":
            with open(self.path, "r", encoding="utf8") as f:
                return f.read()

        if headers is None:
            headers = {}

        redirect_count = 0
        current_url = self

        while True:
            key = (current_url.scheme, current_url.host, current_url.port, current_url.path)
            if key in CACHE:
                body, expires = CACHE[key]
                if time.time() < expires:
                    return body
                else:
                    del CACHE[key]

            s = socket.socket(
                family=socket.AF_INET,
                type=socket.SOCK_STREAM,
                proto=socket.IPPROTO_TCP
            )

            s.connect((current_url.host, current_url.port))
            if current_url.scheme == "https":
                ctx = ssl.create_default_context()
                s = ctx.wrap_socket(s, server_hostname=current_url.host)

            normalized_headers = {
                "Host": current_url.host,
                "Connection": "close",
                "User-Agent": "CustomBrowser"
            }

            for header, value in headers.items():
                normalized_headers[header.title()] = value

            request = "GET {} HTTP/1.1\r\n".format(current_url.path)
            for header, value in normalized_headers.items():
                request += "{}: {}\r\n".format(header, value)
            request += "\r\n"
            s.send(request.encode("utf8"))

            response = s.makefile("r", encoding="utf8", newline="\r\n")

            statusline = response.readline()
            version, status, explanation = statusline.split(" ", 2)
            status = int(status)

            response_headers = {}
            while True:
                line = response.readline()
                if line == "\r\n":
                    break
                header, value = line.split(":", 1)
                response_headers[header.casefold()] = value.strip()

            assert "transfer-encoding" not in response_headers
            assert "content-encoding" not in response_headers

            content = response.read()
            s.close()

            if 300 <= status < 400 and "location" in response_headers:
                location = response_headers.get("location")
                redirect_count += 1
                if redirect_count > 10:
                    raise RedirectLoopError("Infinite redirect loop")

                if location.startswith("/"):
                    location = "{}://{}:{}{}".format(current_url.scheme, current_url.host, current_url.port, location)

                current_url = URL(location)
                continue

            if status == 200 and "cache-control" in response_headers:
                cache_control = response_headers["cache-control"].casefold()
                if cache_control.startswith("max-age=") and "," not in cache_control:
                    max_age = int(cache_control.split("=", 1)[1])
                    CACHE[key] = (content, time.time() + max_age)

            return content

def lex(body):
    out = []
    buffer = ""
    in_tag = False
    for c in body:
        if c == "<":
            in_tag = True
            if buffer:
                out.append(Text(buffer))
            buffer = ""
        elif c == ">":
            in_tag = False
            out.append(Tag(buffer))
            buffer = ""
        else:
            buffer += c
    if not in_tag and buffer:
        out.append(Text(buffer))
    return out

WIDTH, HEIGHT = 800, 600
HSTEP, VSTEP = 13, 18
SCROLL_STEP = 100

def get_font(size, weight, style):
    key = (size, weight, style)
    if key not in FONTS:
        font = tkinter.font.Font(size=size, weight=weight, slant=style)
        FONTS[key] = font
    return FONTS[key]

def get_measure(font, word):
    key = (id(font), word)
    if key not in MEASURES:
        MEASURES[key] = font.measure(word)
    return MEASURES[key]

class Layout:
    def __init__(self, tokens):
        self.display_list = []
        self.cursor_x = HSTEP
        self.cursor_y = VSTEP
        self.weight = "normal"
        self.style = "roman"
        self.size = 12
        self.centering = False
        self.superscript = False
        self.line = []
        for tok in tokens:
            self.token(tok)
        self.flush()

    def token(self, tok):
        if isinstance(tok, Text):
            for word in tok.text.split():
                self.word(word)
        elif tok.tag == "i":
            self.style = "italic"
        elif tok.tag == "/i":
            self.style = "roman"
        elif tok.tag == "b":
            self.weight = "bold"
        elif tok.tag == "/b":
            self.weight = "normal"
        elif tok.tag == "small":
            self.size -= 2
        elif tok.tag == "/small":
            self.size += 2
        elif tok.tag == "big":
            self.size += 4
        elif tok.tag == "/big":
            self.size -= 4
        elif tok.tag == "br":
            self.flush()
        elif tok.tag == "/p":
            self.flush()
            self.cursor_y += VSTEP
        elif tok.tag == "h1 class=\"title\"":
            self.flush()
            self.centering = True
        elif tok.tag == "/h1":
            self.flush()
            self.centering = False
        elif tok.tag == "sup":
            self.superscript = True
        elif tok.tag == "/sup":
            self.superscript = False

    def word(self, word):
        SOFT = "\u00AD"

        size = self.size // 2 if self.superscript else self.size
        font = get_font(size, self.weight, self.style)

        clean = word.replace(SOFT, "")
        w = get_measure(font, clean)

        if self.cursor_x + w <= WIDTH - HSTEP:
            self.line.append((self.cursor_x, word, font, self.superscript))
            self.cursor_x += w + get_measure(font, " ")
            return

        if SOFT not in word:
            self.flush()
            self.line.append((self.cursor_x, word, font, self.superscript))
            self.cursor_x += w + get_measure(font, " ")
            return

        parts = word.split(SOFT)
        longest_idx = None
        current = ""

        for i in range(len(parts) - 1):
            current += parts[i]
            if self.cursor_x + get_measure(font, current + "-") <= WIDTH - HSTEP:
                longest_idx = i
            else:
                break

        if longest_idx is not None:
            prefix = "".join(parts[:longest_idx + 1]) + "-"
            remainder = SOFT.join(parts[longest_idx + 1:])
            self.line.append((self.cursor_x, prefix, font, self.superscript))
            self.flush()
            self.word(remainder)
            return

        if self.cursor_x == HSTEP:
            self.line.append((self.cursor_x, parts[0] + "-", font, self.superscript))
            self.flush()
            self.word(SOFT.join(parts[1:]))
            return

        self.flush()
        self.word(word)

    def flush(self):
        if not self.line:
            return

        metrics = [font.metrics() for x, word, font, sup in self.line]
        max_ascent = max([metric["ascent"] for metric in metrics])
        baseline = self.cursor_y + 1.25 * max_ascent
        top = baseline - max_ascent

        last_x, last_word, last_font, _ = self.line[-1]
        line_width = last_x + get_measure(last_font, last_word) - HSTEP
        offset = (WIDTH - line_width) / 2 - HSTEP if self.centering else 0

        for x, word, font, sup in self.line:
            y = top if sup else baseline - font.metrics("ascent")
            self.display_list.append((x + offset, y, word, font))

        max_descent = max([metric["descent"] for metric in metrics])
        self.cursor_y = baseline + 1.25 * max_descent

        self.cursor_x = HSTEP
        self.line = []

class Browser:
    def __init__(self):
        self.window = tkinter.Tk()
        self.canvas = tkinter.Canvas(
            self.window,
            width=WIDTH,
            height=HEIGHT
        )
        self.canvas.pack(fill="both", expand=True)

        self.scroll = 0
        self.tokens = []
        self.display_list = []

        self.window.bind("<Up>", self.scrollup)
        self.window.bind("<Down>", self.scrolldown)
        self.window.bind("<Configure>", self.resize)

    def load(self, url):
        body = url.request()
        self.tokens = lex(body)
        self.display_list = Layout(self.tokens).display_list
        self.draw()

    def draw(self):
        self.canvas.delete("all")
        for x, y, word, font in self.display_list:
            if y > self.scroll + HEIGHT:
                continue
            if y + font.metrics("linespace") < self.scroll:
                continue
            self.canvas.create_text(x, y - self.scroll, text=word, font=font, anchor="nw")

        page_height = max((y for _, y, _, _ in self.display_list), default=0)

        if page_height <= HEIGHT:
            return

        bar_height = HEIGHT * HEIGHT / page_height
        bar_top = self.scroll * HEIGHT / page_height
        bar_bottom = bar_top + bar_height

        self.canvas.create_rectangle(WIDTH - 8, bar_top, WIDTH, bar_bottom, width=0, fill='blue')

    def scrollup(self, e):
        self.scroll = max(self.scroll - SCROLL_STEP, 0)
        self.draw()

    def scrolldown(self, e):
        self.scroll += SCROLL_STEP
        self.draw()

    def resize(self, e):
        global WIDTH, HEIGHT
        if e.width == WIDTH and e.height == HEIGHT:
            return
        WIDTH = e.width
        HEIGHT = e.height
        self.display_list = Layout(self.tokens).display_list
        self.draw()

class Text:
    def __init__(self, text):
        self.text = text

    def __repr__(self):
        return f"Text('{self.text}')"

class Tag:
    def __init__(self, tag):
        self.tag = tag

    def __repr__(self):
        return f"Tag('{self.tag}')"

def set_parameters(**params):
    global WIDTH, HEIGHT, HSTEP, VSTEP, SCROLL_STEP
    if "WIDTH" in params:
        WIDTH = params["WIDTH"]
    if "HEIGHT" in params:
        HEIGHT = params["HEIGHT"]
    if "HSTEP" in params:
        HSTEP = params["HSTEP"]
    if "VSTEP" in params:
        VSTEP = params["VSTEP"]
    if "SCROLL_STEP" in params:
        SCROLL_STEP = params["SCROLL_STEP"]

if __name__ == "__main__":
    import sys
    Browser().load(URL(sys.argv[1]))
    tkinter.mainloop()
