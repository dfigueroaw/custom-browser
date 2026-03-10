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
    def __init__(self, tree):
        self.display_list = []
        self.cursor_x = HSTEP
        self.cursor_y = VSTEP
        self.weight = "normal"
        self.style = "roman"
        self.size = 12
        self.line = []
        self.recurse(tree)
        self.flush()

    def recurse(self, tree):
        if isinstance(tree, Text):
            for word in tree.text.split():
                self.word(word)
        else:
            self.open_tag(tree.tag)
            for child in tree.children:
                self.recurse(child)
            self.close_tag(tree.tag)

    def open_tag(self, tag):
        if tag == "i":
            self.style = "italic"
        elif tag == "b":
            self.weight = "bold"
        elif tag == "small":
            self.size -= 2
        elif tag == "big":
            self.size += 4
        elif tag == "br":
            self.flush()

    def close_tag(self, tag):
        if tag == "i":
            self.style = "roman"
        elif tag == "b":
            self.weight = "normal"
        elif tag == "small":
            self.size += 2
        elif tag == "big":
            self.size -= 4
        elif tag == "p":
            self.flush()
            self.cursor_y += VSTEP

    def word(self, word):
        SOFT = "\u00AD"

        font = get_font(self.size, self.weight, self.style)

        clean = word.replace(SOFT, "")
        w = get_measure(font, clean)

        if self.cursor_x + w <= WIDTH - HSTEP:
            self.line.append((self.cursor_x, word, font))
            self.cursor_x += w + get_measure(font, " ")
            return

        if SOFT not in word:
            self.flush()
            self.line.append((self.cursor_x, word, font))
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
            self.line.append((self.cursor_x, prefix, font))
            self.flush()
            self.word(remainder)
            return

        if self.cursor_x == HSTEP:
            self.line.append((self.cursor_x, parts[0] + "-", font))
            self.flush()
            self.word(SOFT.join(parts[1:]))
            return

        self.flush()
        self.word(word)

    def flush(self):
        if not self.line:
            return

        metrics = [font.metrics() for x, word, font in self.line]
        max_ascent = max([metric["ascent"] for metric in metrics])
        baseline = self.cursor_y + 1.25 * max_ascent

        for x, word, font in self.line:
            y = baseline - font.metrics("ascent")
            self.display_list.append((x, y, word, font))

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
        self.nodes = None
        self.display_list = []

        self.window.bind("<Up>", self.scrollup)
        self.window.bind("<Down>", self.scrolldown)
        self.window.bind("<Configure>", self.resize)

    def load(self, url):
        body = url.request()
        self.nodes = HTMLParser(body).parse()
        self.display_list = Layout(self.nodes).display_list
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
        self.display_list = Layout(self.nodes).display_list
        self.draw()

class Text:
    def __init__(self, text, parent):
        self.text = text
        self.children = []
        self.parent = parent

    def __repr__(self):
        return repr(self.text)

class Element:
    def __init__(self, tag, attributes, parent):
        self.tag = tag
        self.attributes = attributes
        self.children = []
        self.parent = parent

    def __repr__(self):
        attrs = [" " + k + "=\"" + v + "\"" for k, v in self.attributes.items()]
        attr_str = ""
        for attr in attrs:
            attr_str += attr
        return "<" + self.tag + attr_str + ">"

class HTMLParser:
    SELF_CLOSING_TAGS = [
        "area", "base", "br", "col", "embed", "hr", "img", "input",
        "link", "meta", "param", "source", "track", "wbr",
    ]
    HEAD_TAGS = [
        "base", "basefont", "bgsound", "noscript",
        "link", "meta", "title", "style", "script",
    ]

    def __init__(self, body):
        self.body = body
        self.unfinished = []

    def parse(self):
        buffer = ""
        in_tag = False
        for c in self.body:
            if c == "<":
                in_tag = True
                if buffer:
                    self.add_text(buffer)
                buffer = ""
            elif c == ">":
                in_tag = False
                self.add_tag(buffer)
                buffer = ""
            else:
                buffer += c
        if not in_tag and buffer:
            self.add_text(buffer)
        return self.finish()

    def add_text(self, text):
        if text.isspace():
            return
        self.implicit_tags(None)
        parent = self.unfinished[-1]
        node = Text(text, parent)
        parent.children.append(node)

    def add_tag(self, tag):
        tag, attributes = self.get_attributes(tag)
        if tag.startswith("!"):
            return
        self.implicit_tags(tag)
        if tag.startswith("/"):
            if len(self.unfinished) == 1:
                return
            node = self.unfinished.pop()
            parent = self.unfinished[-1]
            parent.children.append(node)
        elif tag in self.SELF_CLOSING_TAGS:
            parent = self.unfinished[-1]
            node = Element(tag, attributes, parent)
            parent.children.append(node)
        else:
            parent = self.unfinished[-1] if self.unfinished else None
            node = Element(tag, attributes, parent)
            self.unfinished.append(node)

    def finish(self):
        if not self.unfinished:
            self.implicit_tags(None)
        while len(self.unfinished) > 1:
            node = self.unfinished.pop()
            parent = self.unfinished[-1]
            parent.children.append(node)
        return self.unfinished.pop()

    def get_attributes(self, text):
        parts = text.split()
        tag = parts[0].casefold()
        attributes = {}
        for attrpair in parts[1:]:
            if "=" in attrpair:
                key, value = attrpair.split("=", 1)
                if len(value) > 2 and value[0] in ["'", "\""]:
                    value = value[1:-1]
                attributes[key.casefold()] = value
            else:
                attributes[attrpair.casefold()] = ""
        return tag, attributes

    def implicit_tags(self, tag):
        while True:
            open_tags = [node.tag for node in self.unfinished]
            if open_tags == [] and tag != "html":
                self.add_tag("html")
            elif open_tags == ["html"] and tag not in ["head", "body", "/html"]:
                if tag in self.HEAD_TAGS:
                    self.add_tag("head")
                else:
                    self.add_tag("body")
            elif open_tags == ["html", "head"] and tag not in ["/head"] + self.HEAD_TAGS:
                self.add_tag("/head")
            else:
                break

def print_tree(node, indent=0):
    print(" " * indent, node)
    for child in node.children:
        print_tree(child, indent + 2)

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
