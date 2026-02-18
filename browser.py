import socket
import ssl

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

            if 300 <= int(status) < 400 and "location" in response_headers:
                location = response_headers.get("location")
                redirect_count += 1
                if redirect_count > 10:
                    raise RedirectLoopError("Infinite redirect loop")

                if location.startswith("/"):
                    location = "{}://{}:{}{}".format(current_url.scheme, current_url.host, current_url.port, location)

                current_url = URL(location)
                continue

            return content

def show(body):
    in_tag = False
    for c in body:
        if c == "<":
            in_tag = True
        elif c == ">":
            in_tag = False
        elif not in_tag:
            print(c, end="")

def load(url):
    body = url.request()
    show(body)

if __name__ == "__main__":
    import sys
    load(URL(sys.argv[1]))
