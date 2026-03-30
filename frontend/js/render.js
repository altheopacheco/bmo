const SPRITE_COLS = 4;
const FRAME_W = 32;
const FRAME_H = 32;

const VISEME_FRAME = {
    rest:         0,
    closed:       14,
    lip_teeth:    10,
    dental:       10,
    sibilant:     4,
    sh:           8,
    back:         11,
    rounded:      7,
    r_shape:      8,
    smile:        9,
    mid_open:     11,
    open:         2,
    wide_open:    3,
    breathy_open: 11,
    tongue_teeth: 8
};

const canvas = document.getElementById("bmo-mouth");
const ctx = canvas.getContext("2d");

const spriteSheet = new Image();
spriteSheet.src = "/static/sprites/mouth.png";

function getFrameCoords(viseme) {
    const frame = VISEME_FRAME[viseme] ?? 0;
    return {
        sx: (frame % SPRITE_COLS) * FRAME_W,
        sy: Math.floor(frame / SPRITE_COLS) * FRAME_H,
    };
}

function drawFrame(viseme, alpha) {
    const { sx, sy } = getFrameCoords(viseme);
    console.log(sx, sy)
    ctx.globalAlpha = alpha;
    ctx.drawImage(
        spriteSheet,
        sx, sy, FRAME_W, FRAME_H,
        0, 0, canvas.width, canvas.height
    );
}

function renderMouth({ from, to, blend }) {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    drawFrame(from, 1);
    if (blend > 0 && from !== to) {
        drawFrame(to, blend);
    }
    ctx.globalAlpha = 1;
}

function renderRest() {
    renderMouth({ from: "rest", to: "rest", blend: 0 });
}

spriteSheet.onload = () => {
    drawFrame("rest", 1);
};