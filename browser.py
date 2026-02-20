import socket
import ssl
import time
import tkinter

CACHE = {}

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
    text = ""
    in_tag = False
    for c in body:
        if c == "<":
            in_tag = True
        elif c == ">":
            in_tag = False
        elif not in_tag:
            text += c
    return text

WIDTH, HEIGHT = 800, 600
HSTEP, VSTEP = 13, 18
SCROLL_STEP = 100

def layout(text):
    display_list = []
    cursor_x, cursor_y = HSTEP, VSTEP
    for c in text:
        if c == "\n":
            cursor_y += 2 * VSTEP
            cursor_x = HSTEP
            continue
        display_list.append((cursor_x, cursor_y, c))
        cursor_x += HSTEP
        if cursor_x >= WIDTH - HSTEP:
            cursor_y += VSTEP
            cursor_x = HSTEP
    return display_list

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
        self.text = ""
        self.display_list = []

        self.window.bind("<Up>", self.scrollup)
        self.window.bind("<Down>", self.scrolldown)
        self.window.bind("<Configure>", self.resize)

    def load(self, url):
        body = url.request()
        self.text = lex(body)
        self.display_list = layout(self.text)
        self.draw()

    def draw(self):
        self.canvas.delete("all")
        for x, y, c in self.display_list:
            if y > self.scroll + HEIGHT:
                continue
            if y + VSTEP < self.scroll:
                continue
            self.canvas.create_text(x, y - self.scroll, text=c)

    def scrollup(self, e):
        self.scroll = max(self.scroll - SCROLL_STEP, 0)
        self.draw()

    def scrolldown(self, e):
        self.scroll += SCROLL_STEP
        self.draw()

    def resize(self, e):
        global WIDTH, HEIGHT
        WIDTH = e.width
        HEIGHT = e.height
        self.display_list = layout(self.text)
        self.draw()

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
