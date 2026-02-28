# Benchmark Report

Generated: 2026-02-28T12:00:47

## Inputs
- `benchmarks/realtime_backends_groundtruth_bestedit_base.json`
- `benchmarks/realtime_backends_groundtruth_bestedit_small.json`
- `benchmarks/realtime_backends_groundtruth_bestedit_medium.json`
- `benchmarks/realtime_backends_groundtruth_bestedit_largev3.json`
- `benchmarks/realtime_backends_groundtruth_bestedit_voxmlx_fixed.json`

## How To Read WER
- WER = word error rate (0.0 is perfect, 1.0 means roughly one error per reference word).
- Rough guide: <=0.05 excellent, <=0.15 good, <=0.30 usable with edits, >0.30 poor.

## Aggregate By Config

| Config | Samples | Avg WER | Avg CER | Avg Total(s) | Avg First Token(s) | Avg RTF | Quality |
|---|---:|---:|---:|---:|---:|---:|---|
| faster:whisper-base | 5 | 0.169 | 0.127 | 2.348 | 2.348 | 0.144 | usable with edits |
| faster:whisper-large-v3 | 5 | 0.066 | 0.063 | 34.854 | 34.854 | 3.680 | good |
| faster:whisper-medium | 5 | 0.006 | 0.006 | 13.169 | 13.169 | 0.741 | excellent |
| faster:whisper-small | 5 | 0.068 | 0.060 | 4.774 | 4.774 | 0.279 | good |
| voxmlx:mistralai/Voxtral-Mini-4B-Realtime-2602|chunk=80|commit=0.7|idle=1.2 | 5 | 0.804 | 0.791 | 16.867 | 2.114 | 0.970 | poor |
| voxmlx:voxtral-mini-latest|chunk=80|commit=0.7|idle=1.2 | 5 | 0.814 | 0.801 | 16.216 | 1.470 | 0.950 | poor |

## Per-Sample Mistakes

### recordings/2026-02-27/16-10-29/audio.wav

Reference:

Hey, just testing if this works, hopefully it does.

- Config: `faster:whisper-base`
  WER=0.000 CER=0.070 | total=1.97s first=1.97s | edits(sub/ins/del)=3/0/0 (distance=3)
  Hypothesis:
  Hey just testing if this works hopefully it does

- Config: `faster:whisper-large-v3`
  WER=0.000 CER=0.070 | total=68.71s first=68.71s | edits(sub/ins/del)=3/0/0 (distance=3)
  Hypothesis:
  hey just testing if this works hopefully it does

- Config: `faster:whisper-medium`
  WER=0.000 CER=0.000 | total=9.04s first=9.04s | edits(sub/ins/del)=0/0/0 (distance=0)
  Hypothesis:
  Hey, just testing if this works, hopefully it does.

- Config: `faster:whisper-small`
  WER=0.000 CER=0.070 | total=3.57s first=3.57s | edits(sub/ins/del)=3/0/0 (distance=3)
  Hypothesis:
  Hey just testing if this works hopefully it does

- Config: `voxmlx:mistralai/Voxtral-Mini-4B-Realtime-2602|chunk=80|commit=0.7|idle=1.2`
  WER=0.667 CER=0.651 | total=12.18s first=0.96s | edits(sub/ins/del)=0/0/6 (distance=6)
  Hypothesis:
  Hey, just testing

- Config: `voxmlx:voxtral-mini-latest|chunk=80|commit=0.7|idle=1.2`
  WER=0.667 CER=0.651 | total=12.24s first=1.00s | edits(sub/ins/del)=0/0/6 (distance=6)
  Hypothesis:
  Hey, just testing

### recordings/2026-02-27/17-09-26/audio.wav

Reference:

Ok, testing if this transcript works and if it's fast enough.  There is some noise around, so let's see if the transcription is good.  My sentences should be normal, so if you see weird words or stuff like that, that shouldn't make sense, it's probably transcription mistakes, but that's another problem.

- Config: `faster:whisper-base`
  WER=0.196 CER=0.099 | total=1.36s first=1.36s | edits(sub/ins/del)=13/0/4 (distance=17)
  Hypothesis:
  Okay, testing if this transcript works. It's fast enough. There's some noise around. So, I'll receive the transcription. It's good. My sentence should be normal. So, if you see weird words or stuff like that, that shouldn't make sense. It's probably transcription mistakes, but that's another problem.

- Config: `faster:whisper-large-v3`
  WER=0.059 CER=0.040 | total=18.04s first=18.04s | edits(sub/ins/del)=1/0/2 (distance=3)
  Hypothesis:
  Ok, testing if this transcript works and if it's fast enough. There is some noise around, so let's see if the transcription is good. My sentence should be normal, so if you see weird words or stuff that shouldn't make sense, it's probably transcription mistakes, but that's another problem.

- Config: `faster:whisper-medium`
  WER=0.000 CER=0.004 | total=10.14s first=10.14s | edits(sub/ins/del)=1/0/0 (distance=1)
  Hypothesis:
  Ok, testing if this transcript works and if it's fast enough. There is some noise around, so let's see if the transcription is good. My sentences should be normal, so if you see weird words or stuff like that, that shouldn't make sense. It's probably transcription mistakes, but that's another problem.

- Config: `faster:whisper-small`
  WER=0.059 CER=0.020 | total=3.54s first=3.54s | edits(sub/ins/del)=5/0/1 (distance=6)
  Hypothesis:
  Ok, testing if this transcript works and if it's fast enough, there's some noise around. So let's see if the transcription is good. My sentence should be normal, so if you see weird words or stuff like that, that shouldn't make sense. It's probably transcription mistakes, but that's another problem.

- Config: `voxmlx:mistralai/Voxtral-Mini-4B-Realtime-2602|chunk=80|commit=0.7|idle=1.2`
  WER=0.902 CER=0.881 | total=13.55s first=2.33s | edits(sub/ins/del)=1/0/45 (distance=46)
  Hypothesis:
  Okay, testing if this transcript works

- Config: `voxmlx:voxtral-mini-latest|chunk=80|commit=0.7|idle=1.2`
  WER=1.000 CER=0.980 | total=12.18s first=0.96s | edits(sub/ins/del)=1/0/50 (distance=51)
  Hypothesis:
  Okay,

### recordings/2026-02-27/18-17-10/audio.wav

Reference:

Okay, I'm trying again. Let's see if this time the transcription is correct.  I'm doing a bit of a long message. Let's assume this is a message of like, I don't know, maybe 15 seconds.  This causes inverse kinematics in robotics in a very nosy environment. Hopefully this works properly.

- Config: `faster:whisper-base`
  WER=0.160 CER=0.106 | total=1.60s first=1.60s | edits(sub/ins/del)=2/1/6 (distance=9)
  Hypothesis:
  Okay, I'm trying again. Let's see if this time the transcription is correct. I'm doing a bit of a long message. Let's assume this message of like 15 seconds. This causes the inverse kinematics in robotics and a very nosy environment. Hopefully this works properly.

- Config: `faster:whisper-large-v3`
  WER=0.100 CER=0.047 | total=18.42s first=18.42s | edits(sub/ins/del)=3/3/0 (distance=6)
  Hypothesis:
  Okay, I'm trying again. Let's see if this time the transcription is correct. I'm doing a bit of a long message. Let's assume this is a message of like, I don't know, maybe 15 seconds. This is because this is inverse kinematics in robotics, in a very noisy environment. Hopefully this works properly.

- Config: `faster:whisper-medium`
  WER=0.000 CER=0.000 | total=9.87s first=9.87s | edits(sub/ins/del)=0/0/0 (distance=0)
  Hypothesis:
  Okay, I'm trying again. Let's see if this time the transcription is correct. I'm doing a bit of a long message. Let's assume this is a message of like, I don't know, maybe 15 seconds. This causes inverse kinematics in robotics in a very nosy environment. Hopefully this works properly.

- Config: `faster:whisper-small`
  WER=0.040 CER=0.030 | total=3.48s first=3.48s | edits(sub/ins/del)=4/1/0 (distance=5)
  Hypothesis:
  Okay, I'm trying again. Let's see if this time the transcription is correct. I'm doing a bit of a long message Let's assume this is a message of like, I don't know, maybe 15 seconds. This causes inverse kinematics in robotics and in a very noisy environment Hopefully this works properly

- Config: `voxmlx:mistralai/Voxtral-Mini-4B-Realtime-2602|chunk=80|commit=0.7|idle=1.2`
  WER=0.980 CER=0.979 | total=12.37s first=1.15s | edits(sub/ins/del)=0/0/49 (distance=49)
  Hypothesis:
  Okay,

- Config: `voxmlx:voxtral-mini-latest|chunk=80|commit=0.7|idle=1.2`
  WER=0.940 CER=0.941 | total=12.16s first=0.96s | edits(sub/ins/del)=0/0/47 (distance=47)
  Hypothesis:
  Okay, I'm trying

### recordings/2026-02-27/21-48-39/audio.wav

Reference:

Can we first do a bit more research on this?  Like, for example, does MLX allow for streaming?  Or do we need, specifically, whisper streaming for it to work?  And we're only talking about whisper. Are there other options currently?  I mean, this seems to be a very rapidly moving subject.  I hear about a new model that does stuff.  I want you to research recent models that could be better than whisper for us.  Maybe that's not the case because you need to implement something specific for Apple for it to be better.  I need this research phase first.

- Config: `faster:whisper-base`
  WER=0.170 CER=0.123 | total=2.36s first=2.36s | edits(sub/ins/del)=10/6/6 (distance=22)
  Hypothesis:
  Can we first do a bit more research on this? Like, for example, does Ablelex allow for streaming? Or do we need specifically whisper streaming for it to work? And we're only talking about whisper. Are there other options in currently? I mean, this seems to be very rapidly moving subject type. I've been here a week about a new model that I want you to research. Recent models that are better than whisper for us. Maybe that's not the case, because you need to implement something specific for Able to be better. But I need this research phase first.

- Config: `faster:whisper-large-v3`
  WER=0.110 CER=0.116 | total=35.49s first=35.49s | edits(sub/ins/del)=3/7/3 (distance=13)
  Hypothesis:
  Can we first do a bit more research on this? For example, does MLX allow for streaming? Or do we need specifically Whisper streaming for it to work? And we're only talking about Whisper. Are there other options currently? This seems to be a very rapidly moving subject. Every week I hear about a new model that does stuff. I want you to research recent models that could be better than Whisper for us. Maybe that's not the case because you need to implement something specific for Apple for it to be better. But... I don't know. I'm just beginning this research phase first.

- Config: `faster:whisper-medium`
  WER=0.030 CER=0.025 | total=18.63s first=18.63s | edits(sub/ins/del)=0/0/3 (distance=3)
  Hypothesis:
  Can we first do a bit more research on this? For example, does MLX allow for streaming? Or do we need, specifically, whisper streaming for it to work? And we're only talking about whisper. Are there other options currently? This seems to be a very rapidly moving subject. I hear about a new model that does stuff. I want you to research recent models that could be better than whisper for us. Maybe that's not the case because you need to implement something specific for Apple for it to be better. I need this research phase first.

- Config: `faster:whisper-small`
  WER=0.110 CER=0.096 | total=6.47s first=6.47s | edits(sub/ins/del)=3/0/10 (distance=13)
  Hypothesis:
  Can we first do a bit more research on this? For example, does MLX allow for streaming? Or do we need specifically whisper streaming for it to work? And we're only talking about whisper. Are there other options currently? This seems to be a very rapidly moving subject. I hear about a new model that does recent models that are better than whisper for us. Maybe that's not the case because you need to implement something specific for Apple for it to be better. I need this research phase first.

- Config: `voxmlx:mistralai/Voxtral-Mini-4B-Realtime-2602|chunk=80|commit=0.7|idle=1.2`
  WER=0.590 CER=0.570 | total=29.87s first=2.46s | edits(sub/ins/del)=5/1/57 (distance=63)
  Hypothesis:
  Can we first do a bit more research on this? Like, for example, those MLX, allow for streaming or do we need specifically whisper streaming for it to work? And we're only talking about Whisper. Are there other options in currently? I mean, this

- Config: `voxmlx:voxtral-mini-latest|chunk=80|commit=0.7|idle=1.2`
  WER=0.580 CER=0.562 | total=29.57s first=2.25s | edits(sub/ins/del)=5/1/56 (distance=62)
  Hypothesis:
  Can we first do a bit more research on this? Like, for example, those MLX, allow for streaming or do we need specifically whisper streaming for it to work? And we're only talking about Whisper. Are there other options in currently? I mean, this seems

### recordings/2026-02-28/11-16-57/audio.wav

Reference:

Ok, donc je refais un message vocal en français.  J'aimerais qu'on utilise celui-ci pour le benchmark.  Je vais faire exprès d'utiliser des mots, des fois avec des longues pauses.  Je me demande si on peut poser des questions aussi.  Là, l'environnement est très silencieux.  Des fois, il y a des petits bruits de chaise, des trucs comme ça, mais grosso modo là,  c'est un contexte idéal.  Je pourrais peut-être travailler comme ça.  Et oui, je me demande si je peux utiliser du franglais, des mots un peu archotiques.  Tu vois, si je dis qu'est-ce que c'est que ce bordel de merde, est-ce que c'est bien traduit ?  Si je dis à la future, elle n'a pas été débatant, c'est de ma faute.  Tu vois, est-ce que ce genre de phrase fonctionne ?

- Config: `faster:whisper-base`
  WER=0.319 CER=0.239 | total=4.46s first=4.46s | edits(sub/ins/del)=32/1/18 (distance=51)
  Hypothesis:
  Ok, donc je referais un message vocal en français, j'aimerais qu'on te souvienne pour le benchmark. Je vais faire expliquer des mots, des fois avec des longues pauses. Je pense que si on peut poser des questions, la l'environnement est très silencieux pour des fois des petits branches, mais pour ce modo, c'est un contexte idéal, je pourrais te travailler comme ça. Et si je peux utiliser du franglais, des mots un peu arcotiques, tu as 6 dits, qu'est-ce que c'est que ce bordel de merde, ce que c'est bien traduit, si je dis à la future, à la paix de débatant, c'est de ma faute, tu as ce que ce genre de phrases fonctionne.

- Config: `faster:whisper-large-v3`
  WER=0.059 CER=0.044 | total=33.61s first=33.61s | edits(sub/ins/del)=8/4/2 (distance=14)
  Hypothesis:
  Ok, donc je refais un message vocal en français. J'aimerais qu'on utilise celui-ci pour le benchmark. Je vais faire exprès d'utiliser des mots, des fois avec des longues pauses. Je me demande si on peut poser des questions aussi. Là, l'environnement est très silencieux. Bon, des fois, il y a des petits bruits de chaises, des trucs comme ça. Mais grosso modo, là, c'est un contexte idéal. Je pourrais peut-être travailler comme ça. Et je me demande si je peux utiliser du franglais, des mots un peu archotiques. Tu vois, si je dis « qu'est-ce que c'est que ce bordel de merde ? » Est-ce que c'est bien traduit ? Si je dis « la fixture, elle n'a pas été débattante, c'est de ma faute. » Est-ce que ce genre de phrase fonctionne ?

- Config: `faster:whisper-medium`
  WER=0.000 CER=0.000 | total=18.15s first=18.15s | edits(sub/ins/del)=0/0/0 (distance=0)
  Hypothesis:
  Ok, donc je refais un message vocal en français. J'aimerais qu'on utilise celui-ci pour le benchmark. Je vais faire exprès d'utiliser des mots, des fois avec des longues pauses. Je me demande si on peut poser des questions aussi. Là, l'environnement est très silencieux. Des fois, il y a des petits bruits de chaise, des trucs comme ça, mais grosso modo là, c'est un contexte idéal. Je pourrais peut-être travailler comme ça. Et oui, je me demande si je peux utiliser du franglais, des mots un peu archotiques. Tu vois, si je dis qu'est-ce que c'est que ce bordel de merde, est-ce que c'est bien traduit ? Si je dis à la future, elle n'a pas été débatant, c'est de ma faute. Tu vois, est-ce que ce genre de phrase fonctionne ?

- Config: `faster:whisper-small`
  WER=0.133 CER=0.082 | total=6.81s first=6.81s | edits(sub/ins/del)=14/3/4 (distance=21)
  Hypothesis:
  Ok, donc je refais un message vocale en français. J'aimerais que l'on utilise celui-ci pour le benchmark. Je vais faire exploit d'utiliser des mots, des fois avec des longues pauses. Je vais me demander si on peut poser des questions aussi. Là, l'environnement est très silencieux. Des fois, il y a des petits bruit de chaise, des trucs comme ça. Mais pour ce modo, là, c'est un contexte idéal. Je pourrais travailler comme ça. Et oui, effectivement, si je peux utiliser du franglais, des mots un peu arcotiques, tu vois, si je dis qu'est-ce que c'est que ce bordel de merde, est-ce que c'est bien traduit, si je dis que la feature, elle n'a pas été débattant, c'est de ma faute. Tu vois, est-ce que ce genre de phrase fonctionne ?

- Config: `voxmlx:mistralai/Voxtral-Mini-4B-Realtime-2602|chunk=80|commit=0.7|idle=1.2`
  WER=0.881 CER=0.872 | total=16.36s first=3.67s | edits(sub/ins/del)=0/0/117 (distance=117)
  Hypothesis:
  Ok, donc je refais un message vocal en français. J'aimerais qu'on utilise celui-ci pour le

- Config: `voxmlx:voxtral-mini-latest|chunk=80|commit=0.7|idle=1.2`
  WER=0.881 CER=0.872 | total=14.92s first=2.19s | edits(sub/ins/del)=0/0/117 (distance=117)
  Hypothesis:
  Ok, donc je refais un message vocal en français. J'aimerais qu'on utilise celui-ci pour le
