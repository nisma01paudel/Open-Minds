# Demo narration

The demo video is narrated in **Nepali**, which is the right language for the room and
for the product: the system's whole claim is that its output is usable by a Nepali road
office, so the demo should not switch to English to explain itself.

## How it is generated

`scripts/narrate_omnivoice.py` — [OmniVoice](https://github.com/k2-fsa/OmniVoice)
(k2-fsa), a 646-language zero-shot TTS with **171.5 hours of Nepali training data**. It is
a real step up from Piper's single Nepali voice, which is what the project used before.

OmniVoice needs a GPU. This machine's RTX 4050 is stuck after suspend, and the model is
3.27 GB against 2.9 GB of free RAM, so local inference would exhaust memory before it
loaded. The work is therefore sent to the authors' public Space (A10G) through its Gradio
API — the same model, on hardware that can run it.

```bash
pip install gradio_client
python scripts/narrate_omnivoice.py --in reports/video/voice/narration.txt \
    --out reports/video/voice-omni
```

## The one thing that blocks it

The Space runs on ZeroGPU, and **anonymous callers get a small daily quota** — enough for
two lines of this script. After that it returns:

> You have exceeded your ZeroGPU quota (90s requested vs. 0s left). Authenticate with a
> Hugging Face token for more quota.

A free read token from <https://huggingface.co/settings/tokens> raises the quota enough to
finish the ten lines. Set it and re-run; the script skips lines it already has, so it
resumes rather than restarting.

## The script

Ten lines, timed to the video's beats. Numbers are spelled as Nepali words rather than
digits, because TTS mispronounces bare numerals far more often than words.

Full text: `reports/video/voice/narration.txt`.

## Limitation, stated plainly

**Nobody has listened to the output.** Levels and duration can be checked mechanically —
and were: real speech, ~6 s per line, mean volume around −22 dB, no silent stretch — but
pronunciation cannot be verified without ears. A native speaker must check the Nepali
before this ships as the submission video.
