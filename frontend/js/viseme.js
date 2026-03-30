const PHONEME_TO_VISEME = {
    // --- Silence / special ---
    "_": "rest", "^": "rest", " ": "rest",

    // --- Punctuation (treat as rest) ---
    ".": "rest", ",": "rest", "!": "rest", "?": "rest",
    ":": "rest", ";": "rest", "-": "rest",

    // --- Stress / modifiers (IGNORE or rest) ---
    "ˈ": "rest", "ˌ": "rest", "ː": "rest", "ˑ": "rest",
    "̃": "rest", "̩": "rest", "̯": "rest",

    // --- Closed lips ---
    "p": "closed", "b": "closed", "m": "closed",
    "ɓ": "closed", "ʙ": "closed", "ɱ": "closed",

    // --- Lip-teeth ---
    "f": "lip_teeth", "v": "lip_teeth", "ɸ": "lip_teeth", "β": "lip_teeth",

    // --- Dental / alveolar ---
    "t": "dental", "d": "dental", "n": "dental", "l": "dental",
    "θ": "dental", "ð": "dental",
    "ɾ": "dental", "ɽ": "dental", "ɖ": "dental", "ɗ": "dental",

    // --- Sibilants ---
    "s": "sibilant", "z": "sibilant",
    "ʂ": "sibilant", "ʐ": "sibilant",
    "ɕ": "sibilant", "ʑ": "sibilant",

    // --- SH / CH / J ---
    "ʃ": "sh", "ʒ": "sh",
    "ʦ": "sh", "ʧ": "sh", "ʤ": "sh",

    // --- Back consonants ---
    "k": "dental", "ɡ": "dental", "g": "dental",
    "ŋ": "dental", "x": "dental", "ɣ": "dental",

    // --- R-like ---
    "r": "rounded", "ɹ": "rounded", "ɻ": "rounded",
    "ʀ": "rounded", "ʁ": "rounded",

    // --- W / rounded ---
    "w": "rounded", "ʍ": "rounded", "ɥ": "rounded",

    // --- Smile (front vowels) ---
    "i": "smile", "iː": "smile", "ɪ": "smile",
    "e": "smile", "eɪ": "smile", "j": "smile",
    "y": "smile", "ʏ": "smile",

    // --- Mid-open ---
    "ɛ": "mid_open", "ə": "mid_open", "ɜ": "mid_open", "ʌ": "mid_open",
    "ø": "mid_open", "œ": "mid_open", "ɘ": "mid_open", "ɵ": "mid_open",

    // --- Open ---
    "a": "open", "æ": "open", "ɐ": "open",

    // --- Wide open / back vowels ---
    "ɑ": "wide_open", "ɒ": "wide_open", "ɔ": "wide_open",
    "o": "wide_open", "oʊ": "wide_open",

    "u": "rounded", "uː": "rounded", "ʊ": "rounded",

    // --- H (breathy open) ---
    "h": "breathy_open", "ɦ": "breathy_open",
}

const ANTICIPATION = 0.12; // seconds to blend toward next viseme early

let pendingTimeline = null;
let activeTimeline = null;
let animFrame = null;
let activeAudio = null;
let lastViseme = null;

function phonemeToViseme(phoneme) {
    return PHONEME_TO_VISEME[phoneme] ?? "rest"
}

// Called from main.js when viseme_timeline message arrives
function setPendingTimeline(timeline) {
    pendingTimeline = timeline;
}

// Called from audio.js just before blob arrives
function getPendingTimeline() {
    const t = pendingTimeline;
    pendingTimeline = null;
    return t;
}

function startVisemeAnimation(audio, timeline) {
    cancelAnimationFrame(animFrame);
    activeAudio = audio;
    activeTimeline = timeline;
    tick();
}

function stopVisemeAnimation() {
    cancelAnimationFrame(animFrame);
    activeAudio = null;
    activeTimeline = null;
    renderRest();
}

function tick() {
    if (!activeAudio || !activeTimeline) return;

    const t = activeAudio.currentTime;
    const state = sampleTimeline(activeTimeline, t);
    renderMouth(state);

    animFrame = requestAnimationFrame(tick);
}

function sampleTimeline(timeline, t) {
    let currentIndex = 0

    while (
        currentIndex < timeline.length - 1 &&
        t >= timeline[currentIndex].end
    ) {
        currentIndex++;
    }

    if (currentIndex === 0) return { from: lastViseme || "rest", to: "rest", blend: 0 };

    const cur  = timeline[currentIndex];
    const next = timeline[currentIndex + 1] ?? null;

    const anticipateAt = cur.end - ANTICIPATION;
    let blend = 0;

    if (next && t > anticipateAt) {
        const duration = Math.max(cur.end - anticipateAt, 0.001);
        blend = (t - anticipateAt) / duration;
        blend = easeInOut(Math.min(blend, 1));
    }

    return {
        from:  phonemeToViseme(cur.phoneme),
        to:    phonemeToViseme(next?.phoneme) ?? "rest",
        blend,
    };
}

function easeInOut(t) {
    return t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t;
}