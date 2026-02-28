# Benchmark Report

Generated: 2026-02-28T11:51:15

## Inputs
- `benchmarks/realtime_backends_groundtruth_bestedit_medium.json`
- `benchmarks/realtime_backends_groundtruth_bestedit_small.json`
- `benchmarks/realtime_backends_groundtruth_bestedit_base.json`
- `benchmarks/realtime_backends_groundtruth_bestedit_voxmlx_default.json`
- `benchmarks/realtime_backends_groundtruth_bestedit_voxmlx_lowlat.json`

## How To Read WER
- WER = word error rate (0.0 is perfect, 1.0 means roughly one error per reference word).
- Rough guide: <=0.05 excellent, <=0.15 good, <=0.30 usable with edits, >0.30 poor.

## Aggregate By Config

| Config | Samples | Avg WER | Avg CER | Avg Total(s) | Avg First Token(s) | Avg RTF | Quality |
|---|---:|---:|---:|---:|---:|---:|---|
| faster:whisper-base | 5 | 0.169 | 0.127 | 2.348 | 2.348 | 0.144 | usable with edits |
| faster:whisper-medium | 5 | 0.006 | 0.006 | 13.169 | 13.169 | 0.741 | excellent |
| faster:whisper-small | 5 | 0.068 | 0.060 | 4.774 | 4.774 | 0.279 | good |
| voxmlx:voxtral-mini-latest|chunk=80|commit=0.3|idle=0.8 | 5 | 0.842 | 0.843 | 16.906 | 2.533 | 0.955 | poor |
| voxmlx:voxtral-mini-latest|chunk=80|commit=0.7|idle=1.2 | 5 | 0.820 | 0.811 | 16.916 | 2.209 | 0.977 | poor |

## Per-Sample Mistakes

### recordings/2026-02-27/16-10-29/audio.wav

Reference:

Hey, just testing if this works, hopefully it does.

- Config: `faster:whisper-base`
  WER=0.000 CER=0.070 | total=1.97s first=1.97s | edits(sub/ins/del)=3/0/0 (distance=3)
  Hypothesis:
  Hey just testing if this works hopefully it does

- Config: `faster:whisper-medium`
  WER=0.000 CER=0.000 | total=9.04s first=9.04s | edits(sub/ins/del)=0/0/0 (distance=0)
  Hypothesis:
  Hey, just testing if this works, hopefully it does.

- Config: `faster:whisper-small`
  WER=0.000 CER=0.070 | total=3.57s first=3.57s | edits(sub/ins/del)=3/0/0 (distance=3)
  Hypothesis:
  Hey just testing if this works hopefully it does

- Config: `voxmlx:voxtral-mini-latest|chunk=80|commit=0.3|idle=0.8`
  WER=0.778 CER=0.814 | total=11.77s first=0.94s | edits(sub/ins/del)=0/0/7 (distance=7)
  Hypothesis:
  Hey, just

- Config: `voxmlx:voxtral-mini-latest|chunk=80|commit=0.7|idle=1.2`
  WER=0.667 CER=0.651 | total=12.23s first=1.00s | edits(sub/ins/del)=0/0/6 (distance=6)
  Hypothesis:
  Hey, just testing

### recordings/2026-02-27/17-09-26/audio.wav

Reference:

Ok, testing if this transcript works and if it's fast enough.  There is some noise around, so let's see if the transcription is good.  My sentences should be normal, so if you see weird words or stuff like that, that shouldn't make sense, it's probably transcription mistakes, but that's another problem.

- Config: `faster:whisper-base`
  WER=0.196 CER=0.099 | total=1.36s first=1.36s | edits(sub/ins/del)=13/0/4 (distance=17)
  Hypothesis:
  Okay, testing if this transcript works. It's fast enough. There's some noise around. So, I'll receive the transcription. It's good. My sentence should be normal. So, if you see weird words or stuff like that, that shouldn't make sense. It's probably transcription mistakes, but that's another problem.

- Config: `faster:whisper-medium`
  WER=0.000 CER=0.004 | total=10.14s first=10.14s | edits(sub/ins/del)=1/0/0 (distance=1)
  Hypothesis:
  Ok, testing if this transcript works and if it's fast enough. There is some noise around, so let's see if the transcription is good. My sentences should be normal, so if you see weird words or stuff like that, that shouldn't make sense. It's probably transcription mistakes, but that's another problem.

- Config: `faster:whisper-small`
  WER=0.059 CER=0.020 | total=3.54s first=3.54s | edits(sub/ins/del)=5/0/1 (distance=6)
  Hypothesis:
  Ok, testing if this transcript works and if it's fast enough, there's some noise around. So let's see if the transcription is good. My sentence should be normal, so if you see weird words or stuff like that, that shouldn't make sense. It's probably transcription mistakes, but that's another problem.

- Config: `voxmlx:voxtral-mini-latest|chunk=80|commit=0.3|idle=0.8`
  WER=1.000 CER=0.984 | total=11.84s first=1.02s | edits(sub/ins/del)=1/0/50 (distance=51)
  Hypothesis:
  Okay

- Config: `voxmlx:voxtral-mini-latest|chunk=80|commit=0.7|idle=1.2`
  WER=1.000 CER=0.984 | total=12.24s first=1.02s | edits(sub/ins/del)=1/0/50 (distance=51)
  Hypothesis:
  Okay

### recordings/2026-02-27/18-17-10/audio.wav

Reference:

Okay, I'm trying again. Let's see if this time the transcription is correct.  I'm doing a bit of a long message. Let's assume this is a message of like, I don't know, maybe 15 seconds.  This causes inverse kinematics in robotics in a very nosy environment. Hopefully this works properly.

- Config: `faster:whisper-base`
  WER=0.160 CER=0.106 | total=1.60s first=1.60s | edits(sub/ins/del)=2/1/6 (distance=9)
  Hypothesis:
  Okay, I'm trying again. Let's see if this time the transcription is correct. I'm doing a bit of a long message. Let's assume this message of like 15 seconds. This causes the inverse kinematics in robotics and a very nosy environment. Hopefully this works properly.

- Config: `faster:whisper-medium`
  WER=0.000 CER=0.000 | total=9.87s first=9.87s | edits(sub/ins/del)=0/0/0 (distance=0)
  Hypothesis:
  Okay, I'm trying again. Let's see if this time the transcription is correct. I'm doing a bit of a long message. Let's assume this is a message of like, I don't know, maybe 15 seconds. This causes inverse kinematics in robotics in a very nosy environment. Hopefully this works properly.

- Config: `faster:whisper-small`
  WER=0.040 CER=0.030 | total=3.48s first=3.48s | edits(sub/ins/del)=4/1/0 (distance=5)
  Hypothesis:
  Okay, I'm trying again. Let's see if this time the transcription is correct. I'm doing a bit of a long message Let's assume this is a message of like, I don't know, maybe 15 seconds. This causes inverse kinematics in robotics and in a very noisy environment Hopefully this works properly

- Config: `voxmlx:voxtral-mini-latest|chunk=80|commit=0.3|idle=0.8`
  WER=0.960 CER=0.975 | total=13.82s first=2.98s | edits(sub/ins/del)=0/0/48 (distance=48)
  Hypothesis:
  Okay, I

- Config: `voxmlx:voxtral-mini-latest|chunk=80|commit=0.7|idle=1.2`
  WER=0.960 CER=0.975 | total=13.98s first=2.77s | edits(sub/ins/del)=0/0/48 (distance=48)
  Hypothesis:
  Okay, I

### recordings/2026-02-27/21-48-39/audio.wav

Reference:

Can we first do a bit more research on this?  Like, for example, does MLX allow for streaming?  Or do we need, specifically, whisper streaming for it to work?  And we're only talking about whisper. Are there other options currently?  I mean, this seems to be a very rapidly moving subject.  I hear about a new model that does stuff.  I want you to research recent models that could be better than whisper for us.  Maybe that's not the case because you need to implement something specific for Apple for it to be better.  I need this research phase first.

- Config: `faster:whisper-base`
  WER=0.170 CER=0.123 | total=2.36s first=2.36s | edits(sub/ins/del)=10/6/6 (distance=22)
  Hypothesis:
  Can we first do a bit more research on this? Like, for example, does Ablelex allow for streaming? Or do we need specifically whisper streaming for it to work? And we're only talking about whisper. Are there other options in currently? I mean, this seems to be very rapidly moving subject type. I've been here a week about a new model that I want you to research. Recent models that are better than whisper for us. Maybe that's not the case, because you need to implement something specific for Able to be better. But I need this research phase first.

- Config: `faster:whisper-medium`
  WER=0.030 CER=0.025 | total=18.63s first=18.63s | edits(sub/ins/del)=0/0/3 (distance=3)
  Hypothesis:
  Can we first do a bit more research on this? For example, does MLX allow for streaming? Or do we need, specifically, whisper streaming for it to work? And we're only talking about whisper. Are there other options currently? This seems to be a very rapidly moving subject. I hear about a new model that does stuff. I want you to research recent models that could be better than whisper for us. Maybe that's not the case because you need to implement something specific for Apple for it to be better. I need this research phase first.

- Config: `faster:whisper-small`
  WER=0.110 CER=0.096 | total=6.47s first=6.47s | edits(sub/ins/del)=3/0/10 (distance=13)
  Hypothesis:
  Can we first do a bit more research on this? For example, does MLX allow for streaming? Or do we need specifically whisper streaming for it to work? And we're only talking about whisper. Are there other options currently? This seems to be a very rapidly moving subject. I hear about a new model that does recent models that are better than whisper for us. Maybe that's not the case because you need to implement something specific for Apple for it to be better. I need this research phase first.

- Config: `voxmlx:voxtral-mini-latest|chunk=80|commit=0.3|idle=0.8`
  WER=0.590 CER=0.570 | total=29.92s first=2.83s | edits(sub/ins/del)=5/1/57 (distance=63)
  Hypothesis:
  Can we first do a bit more research on this? Like, for example, those MLX, allow for streaming or do we need specifically whisper streaming for it to work? And we're only talking about Whisper. Are there other options in currently? I mean, this

- Config: `voxmlx:voxtral-mini-latest|chunk=80|commit=0.7|idle=1.2`
  WER=0.590 CER=0.570 | total=29.58s first=2.41s | edits(sub/ins/del)=5/1/57 (distance=63)
  Hypothesis:
  Can we first do a bit more research on this? Like, for example, those MLX, allow for streaming or do we need specifically whisper streaming for it to work? And we're only talking about Whisper. Are there other options in currently? I mean, this

### recordings/2026-02-28/11-16-57/audio.wav

Reference:

Ok, donc je refais un message vocal en français.  J'aimerais qu'on utilise celui-ci pour le benchmark.  Je vais faire exprès d'utiliser des mots, des fois avec des longues pauses.  Je me demande si on peut poser des questions aussi.  Là, l'environnement est très silencieux.  Des fois, il y a des petits bruits de chaise, des trucs comme ça, mais grosso modo là,  c'est un contexte idéal.  Je pourrais peut-être travailler comme ça.  Et oui, je me demande si je peux utiliser du franglais, des mots un peu archotiques.  Tu vois, si je dis qu'est-ce que c'est que ce bordel de merde, est-ce que c'est bien traduit ?  Si je dis à la future, elle n'a pas été débatant, c'est de ma faute.  Tu vois, est-ce que ce genre de phrase fonctionne ?

- Config: `faster:whisper-base`
  WER=0.319 CER=0.239 | total=4.46s first=4.46s | edits(sub/ins/del)=32/1/18 (distance=51)
  Hypothesis:
  Ok, donc je referais un message vocal en français, j'aimerais qu'on te souvienne pour le benchmark. Je vais faire expliquer des mots, des fois avec des longues pauses. Je pense que si on peut poser des questions, la l'environnement est très silencieux pour des fois des petits branches, mais pour ce modo, c'est un contexte idéal, je pourrais te travailler comme ça. Et si je peux utiliser du franglais, des mots un peu arcotiques, tu as 6 dits, qu'est-ce que c'est que ce bordel de merde, ce que c'est bien traduit, si je dis à la future, à la paix de débatant, c'est de ma faute, tu as ce que ce genre de phrases fonctionne.

- Config: `faster:whisper-medium`
  WER=0.000 CER=0.000 | total=18.15s first=18.15s | edits(sub/ins/del)=0/0/0 (distance=0)
  Hypothesis:
  Ok, donc je refais un message vocal en français. J'aimerais qu'on utilise celui-ci pour le benchmark. Je vais faire exprès d'utiliser des mots, des fois avec des longues pauses. Je me demande si on peut poser des questions aussi. Là, l'environnement est très silencieux. Des fois, il y a des petits bruits de chaise, des trucs comme ça, mais grosso modo là, c'est un contexte idéal. Je pourrais peut-être travailler comme ça. Et oui, je me demande si je peux utiliser du franglais, des mots un peu archotiques. Tu vois, si je dis qu'est-ce que c'est que ce bordel de merde, est-ce que c'est bien traduit ? Si je dis à la future, elle n'a pas été débatant, c'est de ma faute. Tu vois, est-ce que ce genre de phrase fonctionne ?

- Config: `faster:whisper-small`
  WER=0.133 CER=0.082 | total=6.81s first=6.81s | edits(sub/ins/del)=14/3/4 (distance=21)
  Hypothesis:
  Ok, donc je refais un message vocale en français. J'aimerais que l'on utilise celui-ci pour le benchmark. Je vais faire exploit d'utiliser des mots, des fois avec des longues pauses. Je vais me demander si on peut poser des questions aussi. Là, l'environnement est très silencieux. Des fois, il y a des petits bruit de chaise, des trucs comme ça. Mais pour ce modo, là, c'est un contexte idéal. Je pourrais travailler comme ça. Et oui, effectivement, si je peux utiliser du franglais, des mots un peu arcotiques, tu vois, si je dis qu'est-ce que c'est que ce bordel de merde, est-ce que c'est bien traduit, si je dis que la feature, elle n'a pas été débattant, c'est de ma faute. Tu vois, est-ce que ce genre de phrase fonctionne ?

- Config: `voxmlx:voxtral-mini-latest|chunk=80|commit=0.3|idle=0.8`
  WER=0.881 CER=0.872 | total=17.19s first=4.90s | edits(sub/ins/del)=0/0/117 (distance=117)
  Hypothesis:
  Ok, donc je refais un message vocal en français. J'aimerais qu'on utilise celui-ci pour le

- Config: `voxmlx:voxtral-mini-latest|chunk=80|commit=0.7|idle=1.2`
  WER=0.881 CER=0.872 | total=16.54s first=3.85s | edits(sub/ins/del)=0/0/117 (distance=117)
  Hypothesis:
  Ok, donc je refais un message vocal en français. J'aimerais qu'on utilise celui-ci pour le
