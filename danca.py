#!/usr/bin/env python3
# Duas pessoas dançando em ASCII, no ritmo de "I Wanna Be Yours".
# Sem dependências: só Python 3. Rode num terminal de verdade (não no "Output" do VS Code):
#     python danca.py
# Opções: --sem-som   --loop

import math
import os
import shutil
import subprocess
import sys
import time

COLS, ROWS = 100, 56     # tamanho da tela em caracteres
ZOOM = 1.25              # caracteres por unidade do "mundo"
W = COLS / ZOOM          # largura do mundo (um caractere tem altura = 2 larguras)
FLOOR = 82               # altura do chão no mundo
FPS = 24
DURACAO = 19.6
BEAT = 0.882             # duração de uma batida (s)
BEAT0 = 0.09             # primeira batida (s)

AQUI = os.path.dirname(os.path.abspath(__file__))
MUSICA = os.path.join(AQUI, "musica.wav")

# Cada pessoa: cor do corpo, cor do cabelo, tamanho e detalhes.
# Troque à vontade (ex.: "saia": True, "cabelo_longo": False).
PESSOAS = {
    "A": {"cor": (225, 150, 255), "cabelo": (150, 80, 215), "escala": 0.93,
          "cabelo_longo": True, "saia": False},
    "B": {"cor": (145, 105, 255), "cabelo": (85, 50, 175), "escala": 1.0,
          "cabelo_longo": False, "saia": False},
}

LETRA = [
    (0.2, 3.0, "Maybe I just wanna be yours"),
    (3.3, 5.3, "I wanna be yours"),
    (5.6, 7.8, "I wanna be yours"),
    (8.6, 11.2, "Wanna be yours"),
    (12.0, 13.6, "Wanna be yours"),
    (14.4, 16.4, "Wanna be yours.."),
]
DEDICATORIA = "♥  eu te amo vida  ♥"

CORE = "$@#&%8BWM0QD"
MID = "abdhkpqwmZOJUCLXYzcvunxrj"
EDGE = "|/\\(){}[]!lIt1fj?<>i"


# ---------------------------------------------------------------- utilidades

def clamp(v, a, b):
    return a if v < a else b if v > b else v


def smooth(a, b, t):
    """smoothstep de a até b."""
    if b == a:
        return 1.0 if t >= b else 0.0
    x = clamp((t - a) / (b - a), 0.0, 1.0)
    return x * x * (3 - 2 * x)


def lerp(a, b, k):
    return a + (b - a) * k


def lerp2(p, q, k):
    return (lerp(p[0], q[0], k), lerp(p[1], q[1], k))


def h32(*vals):
    h = 2166136261
    for v in vals:
        h = ((h ^ (v & 0xFFFFFFFF)) * 16777619) & 0xFFFFFFFF
    h ^= h >> 13
    h = (h * 0x5BD1E995) & 0xFFFFFFFF
    return h ^ (h >> 15)


def ik(root, target, a, b, bend):
    """IK de 2 ossos: devolve (cotovelo/joelho, ponta)."""
    dx, dy = target[0] - root[0], target[1] - root[1]
    d = math.hypot(dx, dy)
    d = clamp(d, abs(a - b) + 0.01, a + b - 0.01)
    base = math.atan2(dy, dx)
    cos_a = clamp((a * a + d * d - b * b) / (2 * a * d), -1.0, 1.0)
    ang = base + bend * math.acos(cos_a)
    mid = (root[0] + a * math.cos(ang), root[1] + a * math.sin(ang))
    ang2 = math.atan2(target[1] - mid[1], target[0] - mid[0])
    return mid, (mid[0] + b * math.cos(ang2), mid[1] + b * math.sin(ang2))


# ---------------------------------------------------------------- formas (SDF)

class Capsula:
    def __init__(self, p, q, r, z, cor, fig):
        self.p, self.q, self.r, self.z, self.cor, self.fig = p, q, r, z, cor, fig

    def bbox(self):
        r = self.r + 1
        return (min(self.p[0], self.q[0]) - r, min(self.p[1], self.q[1]) - r,
                max(self.p[0], self.q[0]) + r, max(self.p[1], self.q[1]) + r)

    def sdf(self, x, y):
        px, py = x - self.p[0], y - self.p[1]
        bx, by = self.q[0] - self.p[0], self.q[1] - self.p[1]
        bb = bx * bx + by * by
        k = clamp((px * bx + py * by) / bb, 0.0, 1.0) if bb else 0.0
        return math.hypot(px - bx * k, py - by * k) - self.r


class Elipse:
    def __init__(self, c, rx, ry, z, cor, fig):
        self.c, self.rx, self.ry, self.z, self.cor, self.fig = c, max(rx, 0.3), ry, z, cor, fig

    def bbox(self):
        return (self.c[0] - self.rx - 1, self.c[1] - self.ry - 1,
                self.c[0] + self.rx + 1, self.c[1] + self.ry + 1)

    def sdf(self, x, y):
        nx, ny = (x - self.c[0]) / self.rx, (y - self.c[1]) / self.ry
        return (math.hypot(nx, ny) - 1.0) * min(self.rx, self.ry)


class Trapezio:
    """Saia: topo estreito em y0, base larga em y1."""
    def __init__(self, cx, y0, w0, y1, w1, z, cor, fig):
        self.cx, self.y0, self.w0, self.y1, self.w1 = cx, y0, w0, y1, w1
        self.z, self.cor, self.fig = z, cor, fig

    def bbox(self):
        w = max(self.w0, self.w1) + 1
        return (self.cx - w, self.y0 - 1, self.cx + w, self.y1 + 1)

    def sdf(self, x, y):
        k = clamp((y - self.y0) / (self.y1 - self.y0), 0.0, 1.0)
        w = lerp(self.w0, self.w1, k)
        return max(abs(x - self.cx) - w, self.y0 - y, y - self.y1)


class Coracao:
    def __init__(self, c, s, z, cor):
        self.c, self.s, self.z, self.cor, self.fig = c, max(s, 0.01), z, cor, "heart"

    def bbox(self):
        return (self.c[0] - 1.3 * self.s, self.c[1] - 1.2 * self.s,
                self.c[0] + 1.3 * self.s, self.c[1] + 1.4 * self.s)

    def sdf(self, x, y):
        u, v = (x - self.c[0]) / self.s, -(y - self.c[1]) / self.s + 0.15
        f = (u * u + v * v - 1) ** 3 - u * u * v ** 3
        # aproximação de distância: positivo fora, negativo dentro
        return f * self.s * 1.6 if f > 0 else -min(-f, 1.0) ** 0.35 * self.s * 0.6


# ---------------------------------------------------------------- coreografia

def sway(t):
    """-1..1, troca de lado a cada batida (dois tempos por ciclo)."""
    return math.sin(math.pi * (t - BEAT0) / BEAT)


def pose(t):
    """Posição de cada pessoa no tempo t (em segundos)."""
    s = sway(t)
    cx = W / 2 + 2.2 * s * smooth(0.3, 2.0, t)

    perto = smooth(2.4, 5.0, t)
    abraco = smooth(11.6, 12.8, t)
    dist = lerp(lerp(38, 18, perto), 13.5, abraco)

    giro = 4 * math.pi * smooth(8.5, 11.4, t)          # A gira duas vezes
    giro_vel = smooth(8.5, 9.2, t) * (1 - smooth(10.8, 11.6, t))

    final = smooth(15.6, 17.0, t)
    inclina = 0.10 * abraco + 0.08 * final

    out = {}
    for nome, lado in (("A", -1), ("B", 1)):
        cfg = PESSOAS[nome]
        sc = cfg["escala"]
        hx = cx + lado * dist / 2
        # passinhos: um pé sobe em cada batida, alternando
        fase = (t - BEAT0) / BEAT
        pe_dir = max(0.0, math.sin(math.pi * fase)) if int(math.floor(fase)) % 2 == 0 else 0.0
        pe_esq = max(0.0, -math.sin(math.pi * fase)) if int(math.floor(fase)) % 2 == 1 else 0.0
        bob = 1.1 * abs(math.sin(math.pi * fase))
        out[nome] = {
            "hx": hx, "bob": bob, "sc": sc, "lado": lado,
            "phi": giro if nome == "A" else 0.0,
            "giro_vel": giro_vel if nome == "A" else 0.0,
            "lean": -lado * inclina + 0.04 * s,         # inclina para o par
            "tilt": -lado * (0.12 * abraco + 0.18 * final) + 0.06 * s,
            "pes": (pe_esq * 2.6, pe_dir * 2.6),
            "sway": s,
        }
    return out


def maos(t, p, ombros):
    """Alvos das mãos de A e B (lado de dentro / de fora) para cada fase."""
    A, B = p["A"], p["B"]
    s = sway(t)
    meio_x = (A["hx"] + B["hx"]) / 2

    def soltas(sh_in, sh_out, lado):
        # braços soltos balançando
        return {"in": (sh_in[0] + lado * 3 + s * 1.5, sh_in[1] + 21),
                "out": (sh_out[0] - lado * 3 + s * 1.5, sh_out[1] + 21)}

    alvo = {}
    for nome in "AB":
        lado = p[nome]["lado"]
        alvo[nome] = soltas(ombros[nome]["in"], ombros[nome]["out"], lado)

    # 1) B estende a mão para A
    k = smooth(1.2, 2.6, t) * (1 - smooth(2.6, 3.4, t))
    convite = (B["hx"] - 13, ombros["B"]["in"][1] + 9)
    alvo["B"]["in"] = lerp2(alvo["B"]["in"], convite, k)

    # 2) de mãos dadas, balançando
    k = smooth(2.6, 3.6, t) * (1 - smooth(8.0, 8.6, t))
    dadas = (meio_x, ombros["B"]["in"][1] + 12 - 2.5 * abs(s))
    alvo["A"]["in"] = lerp2(alvo["A"]["in"], dadas, k)
    alvo["B"]["in"] = lerp2(alvo["B"]["in"], dadas, k)

    # 3) giro: as mãos sobem por cima da cabeça de A
    k = smooth(8.0, 8.7, t) * (1 - smooth(11.2, 11.9, t))
    topo = (A["hx"] + 1.5, ombros["A"]["in"][1] - 14)
    alvo["A"]["in"] = lerp2(alvo["A"]["in"], topo, k)
    alvo["B"]["in"] = lerp2(alvo["B"]["in"], topo, k)
    alvo["A"]["out"] = lerp2(alvo["A"]["out"], (A["hx"], ombros["A"]["in"][1] + 12), k)

    # 4) abraço: A com as mãos nos ombros de B, B com as mãos na cintura de A
    k = smooth(11.5, 12.6, t)
    alvo["A"]["in"] = lerp2(alvo["A"]["in"], ombros["B"]["in"], k)
    alvo["A"]["out"] = lerp2(alvo["A"]["out"], (ombros["B"]["in"][0] + 3, ombros["B"]["in"][1] - 1), k)
    cintura_a = (A["hx"] + 3, ombros["A"]["in"][1] + 14)
    alvo["B"]["in"] = lerp2(alvo["B"]["in"], cintura_a, k)
    alvo["B"]["out"] = lerp2(alvo["B"]["out"], (A["hx"] - 2, cintura_a[1] + 1), k)
    return alvo


def montar(t):
    """Gera todas as formas da cena no tempo t."""
    p = pose(t)
    formas = []
    ombros = {}
    esqueleto = {}

    for nome in "AB":
        q = p[nome]
        sc = q["sc"]
        lado = q["lado"]
        cphi = math.cos(q["phi"])
        coxa, canela = 16 * sc, 15 * sc
        hy = FLOOR - (coxa + canela) * 0.96 + q["bob"]
        hip = (q["hx"], hy)
        tronco = 22 * sc
        neck = (hip[0] + math.sin(q["lean"]) * tronco, hip[1] - math.cos(q["lean"]) * tronco)
        ang = q["lean"] + q["tilt"]
        head = (neck[0] + math.sin(ang) * 6.5 * sc, neck[1] - math.cos(ang) * 6.5 * sc)
        sw = 6.3 * sc * (0.35 + 0.65 * abs(cphi))
        sh_in = (neck[0] - lado * sw * (1 if cphi >= 0 else -1), neck[1] + 2.2)
        sh_out = (neck[0] - (sh_in[0] - neck[0]), neck[1] + 2.2)
        ombros[nome] = {"in": sh_in, "out": sh_out}
        esqueleto[nome] = (hip, neck, head, sc, cphi, hy)

    alvos = maos(t, p, ombros)

    for nome in "AB":
        q = p[nome]
        cfg = PESSOAS[nome]
        cor, cor_cab = cfg["cor"], cfg["cabelo"]
        hip, neck, head, sc, cphi, hy = esqueleto[nome]
        lado = q["lado"]
        zb = 10 if nome == "A" else 12
        braco_z = 30 if nome == "A" else 26
        hw = 3.6 * sc * (0.45 + 0.55 * abs(cphi))

        # pernas
        for i, sgn in enumerate((-1, 1)):
            h = (hip[0] + sgn * hw, hip[1])
            pe = (hip[0] + sgn * (5.5 * sc * (0.4 + 0.6 * abs(cphi))) + q["sway"] * 1.2,
                  FLOOR - q["pes"][i])
            joelho, pe = ik(h, pe, 16 * sc, 15 * sc, -sgn * 0.6 if sgn < 0 else 0.6)
            formas.append(Capsula(h, joelho, 3.3 * sc, zb, cor, nome))
            formas.append(Capsula(joelho, pe, 2.7 * sc, zb, cor, nome))
            formas.append(Capsula(pe, (pe[0] + sgn * 2.5, pe[1]), 1.6, zb, cor, nome))

        # tronco
        meio = lerp2(neck, hip, 0.45)
        largura = 5.6 * sc * (0.55 + 0.45 * abs(cphi))
        formas.append(Elipse(lerp2(neck, meio, 0.55), largura, 7.5 * sc, zb + 1, cor, nome))
        formas.append(Capsula(meio, hip, 4.3 * sc * (0.6 + 0.4 * abs(cphi)), zb + 1, cor, nome))
        formas.append(Capsula(neck, (neck[0], neck[1] - 2), 1.8 * sc, zb + 1, cor, nome))

        if cfg["saia"] or q["giro_vel"] > 0:
            roda = q["giro_vel"]
            if cfg["saia"]:
                formas.append(Trapezio(hip[0], hip[1] - 4, 4.5 * sc, hip[1] + 13 + 2 * roda,
                                       (7.5 + 6 * roda) * sc, zb + 2, cor, nome))
            elif roda > 0.05:
                formas.append(Trapezio(hip[0], hip[1] - 2, 4 * sc, hip[1] + 4 + 4 * roda,
                                       (4.5 + 5 * roda) * sc, zb + 2, cor, nome))

        # cabeça e cabelo
        if cfg["cabelo_longo"]:
            costas = 1 - (cphi + 1) / 2   # de costas = 1
            formas.append(Elipse((head[0] - 0.4 * lado, head[1] + 6 * sc), 6.3 * sc,
                                 11 * sc, zb - 1 + 20 * (costas > 0.5), cor_cab, nome))
        formas.append(Elipse(head, 4.7 * sc, 5.6 * sc, zb + 3, cor, nome))
        formas.append(Elipse((head[0], head[1] - 3.4 * sc), 5.0 * sc, 2.8 * sc, zb + 4, cor_cab, nome))

        # braços (IK até as mãos)
        for qual in ("in", "out"):
            sh = ombros[nome][qual]
            alvo = alvos[nome][qual]
            lado_braco = lado if qual == "in" else -lado
            dobra = 1 if lado_braco > 0 else -1
            cot, mao = ik(sh, alvo, 12 * sc, 12 * sc, dobra * 0.9)
            formas.append(Capsula(sh, cot, 2.4 * sc, braco_z, cor, nome))
            formas.append(Capsula(cot, mao, 2.0 * sc, braco_z, cor, nome))
            formas.append(Elipse(mao, 1.8, 1.8, braco_z, cor, nome))

    # coração no final
    k = smooth(15.8, 17.6, t)
    if k > 0:
        top = min(esqueleto["A"][2][1], esqueleto["B"][2][1])
        pulso = 1 + 0.07 * max(0.0, math.sin(2 * math.pi * (t - BEAT0) / BEAT))
        cx = (esqueleto["A"][2][0] + esqueleto["B"][2][0]) / 2
        formas.append(Coracao((cx, top - 9 - 2 * k), 7 * k * pulso, 50, (185, 75, 255)))
    return formas, esqueleto


# ---------------------------------------------------------------- render

def fade(t):
    return smooth(0.0, 1.0, t) * (1 - smooth(DURACAO - 1.0, DURACAO, t))


def frame(t):
    """Devolve uma grade ROWS×COLS de (caractere, (r, g, b)) ou None para vazio."""
    formas, esq = montar(t)
    grade = [[None] * COLS for _ in range(ROWS)]
    zbuf = [[-1] * COLS for _ in range(ROWS)]
    tick = int(t * 12)
    luz = fade(t)

    tops = {n: esq[n][2][1] - 6 for n in "AB"}
    for f in sorted(formas, key=lambda f: f.z):
        x0, y0, x1, y1 = f.bbox()
        c0, c1 = max(0, int(x0 * ZOOM)), min(COLS - 1, int(x1 * ZOOM) + 1)
        r0, r1 = max(0, int(y0 * ZOOM / 2)), min(ROWS - 1, int(y1 * ZOOM / 2) + 1)
        for r in range(r0, r1 + 1):
            y = (2 * r + 1) / ZOOM
            linha, zl = grade[r], zbuf[r]
            for c in range(c0, c1 + 1):
                d = f.sdf((c + 0.5) / ZOOM, y)
                if d >= 0.9 or f.z < zl[c]:
                    continue
                hsh = h32(c, r, tick, f.z)
                if d >= 0:
                    if zl[c] < 0 and hsh % 5 == 0:
                        cor = tuple(int(v * 0.25 * luz) for v in f.cor)
                        linha[c] = (".", cor)
                    continue
                prof = -d
                if prof > 3.2:
                    ch = CORE[hsh % len(CORE)]
                elif prof > 1.3:
                    ch = MID[hsh % len(MID)]
                else:
                    ch = EDGE[hsh % len(EDGE)]
                # mais claro em cima (como uma chama), mais escuro embaixo
                topo = tops.get(f.fig, y - 10)
                alt = clamp((y - topo) / (FLOOR - topo), 0.0, 1.0)
                b = clamp(0.62 + 0.14 * prof, 0.62, 1.0) * (1.12 - 0.42 * alt)
                if prof <= 1.3:
                    b *= 0.6          # contorno mais escuro separa as partes do corpo
                b *= 0.85 + 0.15 * ((hsh >> 8) % 100) / 100
                b *= luz
                linha[c] = (ch, tuple(int(clamp(v * b, 0, 255)) for v in f.cor))
                zl[c] = f.z

    # reflexo no chão
    rf = int(FLOOR * ZOOM / 2)
    for k in range(1, 4):
        if rf + k >= ROWS:
            break
        for c in range(COLS):
            src = grade[rf - k][c] if rf - k >= 0 else None
            if src and src[0] != "." and h32(c, k, tick) % 3:
                grade[rf + k][c] = (src[0], tuple(int(v * 0.22 / k) for v in src[1]))

    # coraçõezinhos subindo
    if t > 11.8:
        for i in range(26):
            nasc = 11.8 + (h32(i, 7) % 1000) / 1000 * 6.5
            if t < nasc:
                continue
            vida = t - nasc
            x = W / 2 + ((h32(i, 3) % 1000) / 1000 - 0.5) * 44 + 2 * math.sin(vida * 2 + i)
            y = FLOOR - 20 - vida * (6 + h32(i, 5) % 7)
            r, c = int(y * ZOOM / 2), int(x * ZOOM)
            if 9 <= r < ROWS and 0 <= c < COLS:
                ch = "♥" if i % 3 else "*"
                a = clamp(1.2 - vida / 3.5, 0, 1) * luz
                grade[r][c] = (ch, (int(200 * a), int(110 * a), int(255 * a)))

    # "terminal" com a letra digitando
    cab = '[Running] python -u "danca.py"'
    escrever(grade, 1, 2, cab[: int(len(cab) * smooth(0, 0.4, t) + 0.999)], (140, 120, 225))
    for i, (ini, fim, txt) in enumerate(LETRA):
        if t < ini:
            break
        n = int(len(txt) * clamp((t - ini) / (fim - ini), 0, 1) + 0.999)
        escrever(grade, 3 + i, 2, txt[:n], tuple(int(v * luz) for v in (215, 200, 255)))

    # dedicatória
    if t > 16.4:
        n = int(len(DEDICATORIA) * clamp((t - 16.4) / 1.6, 0, 1) + 0.999)
        txt = DEDICATORIA[:n]
        escrever(grade, ROWS - 1, (COLS - len(DEDICATORIA)) // 2, txt,
                 tuple(int(v * luz) for v in (225, 195, 255)))
    return grade


def escrever(grade, r, c, txt, cor):
    for i, ch in enumerate(txt):
        if 0 <= c + i < COLS:
            grade[r][c + i] = (ch, cor)


def ansi(grade):
    partes = ["\x1b[H"]
    ultima = None
    for linha in grade:
        for cel in linha:
            if cel is None:
                partes.append(" ")
                continue
            ch, (r, g, b) = cel
            cor = (r >> 3 << 3, g >> 3 << 3, b >> 3 << 3)
            if cor != ultima:
                partes.append("\x1b[38;2;%d;%d;%dm" % cor)
                ultima = cor
            partes.append(ch)
        partes.append("\n")
    partes.append("\x1b[0m")
    return "".join(partes)


# ---------------------------------------------------------------- som

def tocar(caminho):
    if not os.path.exists(caminho):
        return None
    if sys.platform.startswith("win"):
        import winsound
        winsound.PlaySound(caminho, winsound.SND_FILENAME | winsound.SND_ASYNC)
        return "winsound"
    cmds = [["afplay", caminho]] if sys.platform == "darwin" else [
        ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", caminho],
        ["paplay", caminho], ["aplay", "-q", caminho]]
    for cmd in cmds:
        if shutil.which(cmd[0]):
            return subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return None


def parar(player):
    if player == "winsound":
        import winsound
        winsound.PlaySound(None, 0)
    elif player is not None:
        player.terminate()


def main():
    som = "--sem-som" not in sys.argv
    loop = "--loop" in sys.argv
    if sys.platform.startswith("win"):
        os.system("")  # liga as cores ANSI no Windows
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    cols, rows = shutil.get_terminal_size((COLS, ROWS))
    if cols < COLS or rows < ROWS + 1:
        print("Aumente o terminal para pelo menos %dx%d (agora: %dx%d)." % (COLS, ROWS + 1, cols, rows))
        print("Dica: maximize a janela ou diminua a fonte com Ctrl e '-'.")
        if sys.stdin.isatty():
            input("Enter para continuar mesmo assim...")

    sys.stdout.write("\x1b[?25l\x1b[2J")
    player = None
    try:
        while True:
            player = tocar(MUSICA) if som else None
            t0 = time.perf_counter()
            while True:
                t = time.perf_counter() - t0
                if t > DURACAO:
                    break
                sys.stdout.write(ansi(frame(t)))
                sys.stdout.flush()
                espera = (int(t * FPS) + 1) / FPS - (time.perf_counter() - t0)
                if espera > 0:
                    time.sleep(espera)
            parar(player)
            if not loop:
                break
    except KeyboardInterrupt:
        parar(player)
    finally:
        sys.stdout.write("\x1b[0m\x1b[?25h\n")


if __name__ == "__main__":
    main()
