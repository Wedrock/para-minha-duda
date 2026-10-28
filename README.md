# para minha Duda ♥

Duas pessoas dançando em ASCII no ritmo de "I Wanna Be Yours", feito só com código.

## Abrir no navegador

Abra o `index.html` no navegador, no computador ou no celular, e toque no botão de play. A música já vem dentro do arquivo.

São duas músicas: "I Wanna Be Yours" e depois "Te Vivo". No fim da primeira aparece o link "próxima música". Para abrir direto na segunda, use o endereço com `#te-vivo` no final.

Na segunda, a dança é de salão sertaneja, devagar: "dois pra lá, dois pra cá" abraçadinhos, um giro, uma abertura de mãos dadas, uma inclinada pra trás (cambré) e o abraço final.

Para ter um link, ative o GitHub Pages em Settings → Pages (branch `master`, pasta `/`).

## Rodar no terminal

```
python danca.py
```

- Só precisa de Python 3, sem instalar nada. O som toca com `winsound` no Windows, `afplay` no macOS e `ffplay`/`paplay`/`aplay` no Linux.
- Use um terminal de verdade (Windows Terminal, o terminal integrado do VS Code, o Terminal do macOS). A aba "Output" do VS Code não mostra as cores.
- A animação ocupa 100×57 caracteres. Se não couber, maximize a janela ou diminua a fonte com `Ctrl` e `-`.
- Opções: `--loop` repete sem parar e `--sem-som` roda sem música.

## Gerar o vídeo (para o celular)

```
pip install pillow
python render_video.py
```

Isso cria o `danca.mp4` em formato vertical (1080×1920), já com a música. Precisa ter o `ffmpeg` instalado.

## Personalizar

No topo do `danca.py`:

- `PESSOAS`: cores, altura, cabelo longo ou curto e saia de cada pessoa.
- `LETRA`: os versos e quando cada um aparece.
- `DEDICATORIA`: a frase do final.
