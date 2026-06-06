import machine
import time
import network
import socket
import random

# =========================================================
# CONFIGURATION
# =========================================================

SKULL = 1
SSID = "Skull" + str(SKULL)

LED1_R = 18
LED1_G = 16
LED1_B = 17

LED2_R = 22
LED2_G = 21
LED2_B = 23

BUZZER_PIN = 25
BUTTON_PIN = 27

MAX_CLIENTS = 8
LOCK_TIMES = [30, 60, 120]

# =========================================================
# QUESTIONS PYTHON SELON LA CARTE
# =========================================================

QUESTIONS = {
    1: {
        "place": "Portail Nord",
        "q": "self.r = machine.Pin(16, machine.Pin.OUT)<br><br>Cette ligne initialise :",
        "a": ["La LED rouge", "Le WiFi", "Un bouton", "Le JSON"],
        "c": 0,
        "next": "Va au Crâne 2 : Carré I — Pommiers. Cherche le réseau WiFi Skull2."
    },
    2: {
        "place": "Carré I — Pommiers",
        "q": "ap.config(essid=SSID, authmode=0, channel=6)<br><br>Que fait authmode=0 ?",
        "a": ["Chiffrement WPA2", "Réseau ouvert sans mot de passe", "Limite les utilisateurs", "Choisit le canal WiFi"],
        "c": 1,
        "next": "Va au Crâne 3 : Carré II — Poiriers. Cherche le réseau WiFi Skull3."
    },
    3: {
        "place": "Carré II — Poiriers",
        "q": "Que retourne ap.config('essid') ?",
        "a": ["Le mot de passe", "Le nom du réseau WiFi", "L'adresse IP", "Le canal"],
        "c": 1,
        "next": "Va au Crâne 4 : Bassin Central. Cherche le réseau WiFi Skull4."
    },
    4: {
        "place": "Bassin Central",
        "q": "def locked(self):<br>&nbsp;&nbsp;&nbsp;&nbsp;return self.w >= 3 or time.time() < self.t<br><br>Que signifie self.w >= 3 ?",
        "a": ["3 bonnes réponses", "3 tentatives échouées", "3 utilisateurs connectés", "3 minutes"],
        "c": 1,
        "next": "Va au Crâne 5 : Carré III — Légumes. Cherche le réseau WiFi Skull5."
    },
    5: {
        "place": "Carré III — Légumes",
        "q": "if 'POST' in req and 'a=' in req:<br>&nbsp;&nbsp;&nbsp;&nbsp;ans = int(req.split('a=')[1].split('&')[0])<br><br>Que parse ce code ?",
        "a": ["Le WiFi SSID", "La réponse envoyée par l'utilisateur", "L'en-tête HTTP", "Le numéro du crâne"],
        "c": 1,
        "next": "Va au Crâne 6 : Carré IV — Pêchers. Cherche le réseau WiFi Skull6."
    },
    6: {
        "place": "Carré IV — Pêchers",
        "q": "class Game:<br>&nbsp;&nbsp;&nbsp;&nbsp;def reset(self):<br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.w = 0<br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.t = 0<br><br>Pourquoi reset() remet self.w à 0 ?",
        "a": ["Pour vider la mémoire", "Pour permettre à une nouvelle équipe de jouer", "Pour éteindre la LED", "Pour redémarrer l'ESP32"],
        "c": 1,
        "next": "Va au Crâne 7 : Cabane du Jardinier. Cherche le réseau WiFi Skull7."
    },
    7: {
        "place": "Cabane du Jardinier",
        "q": "c.send('HTTP/1.1 200 OK...'+html)<br>c.close()<br><br>Que fait c.close() ?",
        "a": ["Éteint la LED", "Ferme la connexion TCP avec le navigateur", "Redémarre l'ESP32", "Efface la mémoire"],
        "c": 1,
        "next": "Félicitations ! Le parcours est terminé. Le trésor se trouve dans la boîte rouge marquée FINALE."
    }
}

# =========================================================
# LED RGB DOUBLE
# Cathode commune : 0 = ON, 1 = OFF
# =========================================================

class LED:
    def __init__(self):
        self.leds = [
            {"r": machine.Pin(LED1_R, machine.Pin.OUT), "g": machine.Pin(LED1_G, machine.Pin.OUT), "b": machine.Pin(LED1_B, machine.Pin.OUT)},
            {"r": machine.Pin(LED2_R, machine.Pin.OUT), "g": machine.Pin(LED2_G, machine.Pin.OUT), "b": machine.Pin(LED2_B, machine.Pin.OUT)}
        ]
        self.blue()

    def off(self):
        for led in self.leds:
            led["r"].value(1)
            led["g"].value(1)
            led["b"].value(1)

    def blue(self):
        self.off()
        for led in self.leds:
            led["b"].value(0)

    def green(self):
        for _ in range(5):
            self.off()
            for led in self.leds:
                led["g"].value(0)
            time.sleep(0.25)
            self.off()
            time.sleep(0.25)
        self.blue()

    def red(self):
        for _ in range(3):
            self.off()
            for led in self.leds:
                led["r"].value(0)
            time.sleep(0.25)
            self.off()
            time.sleep(0.25)
        self.blue()

# =========================================================
# BUZZER
# =========================================================

class Buzzer:
    def __init__(self):
        self.pin = machine.Pin(BUZZER_PIN, machine.Pin.OUT)
        self.off()

    def off(self):
        self.pin.value(0)

    def beep(self, duration):
        self.pin.value(1)
        time.sleep(duration)
        self.pin.value(0)

    def correct(self):
        self.beep(0.10)
        time.sleep(0.08)
        self.beep(0.10)
        time.sleep(0.08)
        self.beep(0.30)

    def wrong(self):
        self.beep(0.25)
        time.sleep(0.10)
        self.beep(0.25)

    def locked(self):
        self.beep(0.60)

    def reset(self):
        self.beep(0.10)

# =========================================================
# GAME
# =========================================================

class Game:
    def __init__(self):
        self.reset()

    def reset(self):
        self.errors = 0
        self.lock_until = 0
        self.score = 0
        self.start_time = time.time()
        self.question = QUESTIONS[SKULL]
        print("[GAME RESET]")

    def wrong(self):
        self.errors += 1
        delay = LOCK_TIMES[min(self.errors - 1, len(LOCK_TIMES) - 1)]
        self.lock_until = time.time() + delay

    def locked(self):
        return self.errors >= 3 or time.time() < self.lock_until

    def remaining(self):
        if self.errors >= 3:
            return 0
        return max(0, int(self.lock_until - time.time()))

    def elapsed(self):
        return int(time.time() - self.start_time)

# =========================================================
# HTML
# =========================================================

def html_page(content):
    return """<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{}</title>
<style>
* {{
    box-sizing:border-box;
}}
body {{
    margin:0;
    min-height:100vh;
    font-family:Georgia,serif;
    background:
        radial-gradient(circle at top left, rgba(250,204,21,.25), transparent 30%),
        radial-gradient(circle at bottom right, rgba(120,53,15,.35), transparent 35%),
        linear-gradient(135deg,#2c1a0e,#5a3a1a);
    color:#2a1000;
    display:flex;
    align-items:center;
    justify-content:center;
    padding:18px;
}}
.card {{
    width:100%;
    max-width:540px;
    background:#e8d5a3;
    border:3px solid #5a3a1a;
    border-radius:18px;
    padding:26px;
    text-align:center;
    box-shadow:0 20px 60px rgba(0,0,0,.55);
}}
.badge {{
    display:inline-block;
    padding:8px 14px;
    border-radius:999px;
    background:#5a3a1a;
    color:#facc15;
    font-weight:bold;
    font-size:13px;
    letter-spacing:1px;
}}
h1 {{
    margin:14px 0 6px;
    color:#3a1a00;
    font-size:28px;
}}
.place {{
    color:#6b3d10;
    font-size:15px;
    font-weight:bold;
    margin-bottom:12px;
}}
.question {{
    margin:18px 0;
    padding:18px;
    border-radius:12px;
    background:rgba(255,255,255,.32);
    border:1px dashed #7a4a18;
    font-size:17px;
    line-height:1.6;
}}
button {{
    width:100%;
    padding:15px;
    margin:9px 0;
    border:none;
    border-radius:12px;
    background:#5a3a1a;
    color:#f8e7b5;
    font-size:16px;
    font-weight:bold;
}}
button:active {{
    transform:scale(.98);
}}
.success {{
    color:#166534;
}}
.error {{
    color:#991b1b;
}}
.locked {{
    color:#b45309;
}}
.next {{
    margin:16px 0;
    padding:16px;
    border-radius:12px;
    background:rgba(90,58,26,.12);
    border:1px solid #7a4a18;
    color:#3a1a00;
    font-size:18px;
    font-weight:bold;
    line-height:1.5;
}}
.small {{
    color:#6b3d10;
    font-size:14px;
}}
.footer-note {{
    margin-top:18px;
    font-size:12px;
    color:#6b3d10;
}}
</style>
</head>
<body>
<div class="card">
{}
<div class="footer-note">Chasse au Trésor · La Roche-Guyon · Skull WiFi</div>
</div>
</body>
</html>""".format(SSID, content)

# =========================================================
# WIFI
# =========================================================

def start_wifi():
    ap = network.WLAN(network.AP_IF)
    ap.active(True)
    ap.config(
        essid=SSID,
        authmode=0,
        channel=6,
        max_clients=MAX_CLIENTS
    )
    print("AP READY:", ap.ifconfig())
    print("WiFi:", SSID)
    return ap

# =========================================================
# DNS CAPTIVE PORTAL
# =========================================================

def start_dns():
    dns_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    dns_socket.bind(("0.0.0.0", 53))
    dns_socket.setblocking(False)
    return dns_socket

def handle_dns(dns_socket):
    try:
        data, addr = dns_socket.recvfrom(512)
        response = bytearray(data)
        response[2] |= 0x80
        response[3] |= 0x80
        response += b'\xc0\x0c\x00\x01\x00\x01\x00\x00\x00\x3c\x00\x04'
        response += b'\xc0\xa8\x04\x01'
        dns_socket.sendto(response, addr)
    except:
        pass

# =========================================================
# WEB SERVER
# =========================================================

def start_web_server():
    server = socket.socket()
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("", 80))
    server.listen(1)
    server.settimeout(0.5)
    print("WEB SERVER READY")
    return server

def get_answer(req):
    if "POST" in req and "a=" in req:
        try:
            return int(req.split("a=")[1].split("&")[0].split(" ")[0])
        except:
            return -1
    return -1

def render_question_page(game):
    q = game.question
    content = """
    <span class="badge">CRÂNE {}</span>
    <h1>{}</h1>
    <div class="place">{}</div>
    <p class="small">Réponds à la question Python pour continuer.</p>
    <div class="question">{}</div>
    """.format(SKULL, SSID, q["place"], q["q"])

    if game.locked():
        content += """
        <h2 class="locked">Crâne verrouillé</h2>
        <p>Temps restant : {} secondes</p>
        <p class="small">Erreurs : {}/3</p>
        """.format(game.remaining(), game.errors)
    else:
        content += "<form method='POST'>"
        for i, answer in enumerate(q["a"]):
            content += '<button name="a" value="{}">{}</button>'.format(i, answer)
        content += "</form>"

    return content

def render_answer_page(game, led, buzzer, answer):
    q = game.question

    if game.locked():
        buzzer.locked()
        return """
        <h1 class="locked">CRÂNE VERROUILLÉ</h1>
        <p>Temps restant : {} secondes</p>
        <p class="small">Nombre d'erreurs : {}/3</p>
        """.format(game.remaining(), game.errors)

    if answer == q["c"]:
        game.score += 10
        content = """
        <span class="badge">MISSION VALIDÉE</span>
        <h1 class="success">Bonne réponse</h1>
        <p class="small">Indice de progression :</p>
        <div class="next">{}</div>
        <p class="small">Score : {} points · Temps : {} secondes</p>
        """.format(q["next"], game.score, game.elapsed())

        led.green()
        buzzer.correct()
        game.reset()
        return content

    game.wrong()
    content = """
    <span class="badge">ESSAI MANQUÉ</span>
    <h1 class="error">Mauvaise réponse</h1>
    <p>Attente : {} secondes.</p>
    <p class="small">Erreur {}/3</p>
    """.format(game.remaining(), game.errors)

    led.red()
    buzzer.wrong()
    return content

def handle_client(server, game, led, buzzer):
    try:
        client, addr = server.accept()
        req = client.recv(2048).decode()
        first_line = req.split("\r\n")[0]

        if (
            "generate_204" in req or
            "gen_204" in req or
            "connecttest.txt" in req or
            "ncsi.txt" in req
        ):
            client.send("HTTP/1.1 302 Found\r\nLocation: http://192.168.4.1/\r\n\r\n")
            client.close()
            return

        if (
            "hotspot-detect.html" in req or
            "library/test/success.html" in req
        ):
            client.send(
                "HTTP/1.1 200 OK\r\nContent-Type:text/html\r\n\r\n"
                "<html><head><meta http-equiv='refresh' content='0; url=http://192.168.4.1/'></head><body>Redirect</body></html>"
            )
            client.close()
            return

        if "GET / " not in first_line and "POST / " not in first_line:
            client.send("HTTP/1.1 302 Found\r\nLocation: http://192.168.4.1/\r\n\r\n")
            client.close()
            return

        if "POST" in req:
            answer = get_answer(req)
            content = render_answer_page(game, led, buzzer, answer)
        else:
            content = render_question_page(game)

        page = html_page(content)
        response = "HTTP/1.1 200 OK\r\nContent-Type:text/html\r\n\r\n" + page
        client.send(response)
        client.close()

    except OSError:
        pass

# =========================================================
# INITIALISATION
# =========================================================

start_wifi()
dns_socket = start_dns()
web_server = start_web_server()

led = LED()
buzzer = Buzzer()
game = Game()

button = machine.Pin(BUTTON_PIN, machine.Pin.IN, machine.Pin.PULL_DOWN)
last_button = 0

print("SYSTEM READY")
print("Connectez-vous au WiFi :", SSID)

# =========================================================
# BOUCLE PRINCIPALE
# =========================================================

while True:
    handle_dns(dns_socket)
    handle_client(web_server, game, led, buzzer)

    if button.value() == 1:
        now = time.time()
        if now - last_button > 2:
            print("[TACTILE RESET]")
            game.reset()
            led.blue()
            buzzer.reset()
            last_button = now

    time.sleep(0.02)