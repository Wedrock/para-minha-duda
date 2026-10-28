#!/usr/bin/env python3
# Gera danca.mp4 (vertical, para celular) a partir da mesma animação do danca.py.
# Precisa de: pip install pillow  +  ffmpeg instalado.
#     python render_video.py            -> danca.mp4
#     python render_video.py 12.5       -> só um quadro em quadro.png (para testar)

import os
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont

import danca

LARG, ALT = 1080, 1920
CW, CH = LARG / danca.COLS, 2 * LARG / danca.COLS    # célula 1:2
FPS = 30
FONTES = ["DejaVuSansMono.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
          "consola.ttf", "Menlo.ttc"]


def fonte():
    for f in FONTES:
        try:
            return ImageFont.truetype(f, int(CH * 0.62))
        except OSError:
            pass
    return ImageFont.load_default()


def desenhar(t, font):
    img = Image.new("RGB", (LARG, ALT), (6, 4, 10))
    d = ImageDraw.Draw(img)
    topo = (ALT - CH * danca.ROWS) / 2
    for r, linha in enumerate(danca.frame(t)):
        y = topo + r * CH + CH / 2
        for c, cel in enumerate(linha):
            if cel:
                d.text((c * CW + CW / 2, y), cel[0], fill=cel[1], font=font, anchor="mm")
    return img


def main():
    font = fonte()
    if len(sys.argv) > 1:
        desenhar(float(sys.argv[1]), font).save("quadro.png")
        return
    aqui = os.path.dirname(os.path.abspath(__file__))
    ff = subprocess.Popen([
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (LARG, ALT), "-r", str(FPS), "-i", "-",
        "-i", os.path.join(aqui, "musica.wav"),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-c:a", "aac", "-b:a", "160k",
        "-shortest", os.path.join(aqui, "danca.mp4")], stdin=subprocess.PIPE)
    n = int(danca.DURACAO * FPS)
    for i in range(n):
        ff.stdin.write(desenhar(i / FPS, font).tobytes())
        print("\r%d/%d" % (i + 1, n), end="", flush=True)
    ff.stdin.close()
    ff.wait()
    print("\npronto: danca.mp4")


if __name__ == "__main__":
    main()
