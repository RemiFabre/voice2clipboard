# Ground Truth Curation Pack

- Source manifest: `benchmarks/manifest_groundtruth_seed_short.jsonl`
- JSON bundle: `benchmarks/groundtruth_pack_short_20260228_112412.json`
- Annotation template: `benchmarks/groundtruth_pack_short_20260228_112412_annotations.jsonl`
- Editable matrix CSV: `benchmarks/groundtruth_pack_short_20260228_112412_matrix.csv`

For each sample, choose the best candidate and manually correct into annotation template.

## Sample 1

Audio: `recordings/2026-02-27/16-10-29/audio.wav`

### voxmlx:voxtral-mini-latest

- total_s: `12.24`
- first_token_s: `1.02`

Hey, just

### faster:whisper-medium

- total_s: `8.97`
- first_token_s: `8.97`

Hey, just testing if this works, hopefully it does.

### faster:whisper-small

- total_s: `3.59`
- first_token_s: `3.59`

Hey just testing if this works hopefully it does

### faster:whisper-base

- total_s: `1.73`
- first_token_s: `1.73`

Hey just testing if this works hopefully it does

## Sample 2

Audio: `recordings/2026-02-27/17-09-26/audio.wav`

### voxmlx:voxtral-mini-latest

- total_s: `12.33`
- first_token_s: `1.10`

Okay,

### faster:whisper-medium

- total_s: `10.02`
- first_token_s: `10.02`

Ok, testing if this transcript works and if it's fast enough.  There is some noise around, so let's see if the transcription is good.  My sentences should be normal, so if you see weird words or stuff like that, that shouldn't make sense.  It's probably transcription mistakes, but that's another problem.

### faster:whisper-small

- total_s: `3.53`
- first_token_s: `3.53`

Ok, testing if this transcript works and if it's fast enough, there's some noise around.  So let's see if the transcription is good.  My sentence should be normal, so if you see weird words or stuff like that, that shouldn't make sense.  It's probably transcription mistakes, but that's another problem.

### faster:whisper-base

- total_s: `1.37`
- first_token_s: `1.37`

Okay, testing if this transcript works.  It's fast enough.  There's some noise around.  So, I'll receive the transcription.  It's good.  My sentence should be normal.  So, if you see weird words or stuff like that, that shouldn't make sense.  It's probably transcription mistakes, but that's another problem.

## Sample 3

Audio: `recordings/2026-02-27/18-17-10/audio.wav`

### voxmlx:voxtral-mini-latest

- total_s: `14.29`
- first_token_s: `3.08`

Okay, I

### faster:whisper-medium

- total_s: `9.99`
- first_token_s: `9.99`

Okay, I'm trying again. Let's see if this time the transcription is correct.  I'm doing a bit of a long message. Let's assume this is a message of like, I don't know, maybe 15 seconds.  This causes inverse kinematics in robotics in a very nosy environment. Hopefully this works properly.

### faster:whisper-small

- total_s: `3.50`
- first_token_s: `3.50`

Okay, I'm trying again. Let's see if this time the transcription is correct. I'm doing a bit of a long message  Let's assume this is a message of like, I don't know, maybe 15 seconds. This causes inverse kinematics in robotics and in a very noisy environment  Hopefully this works properly

### faster:whisper-base

- total_s: `1.63`
- first_token_s: `1.63`

Okay, I'm trying again. Let's see if this time the transcription is correct. I'm doing a bit of a long message. Let's assume this message of like 15 seconds.  This causes the inverse kinematics in robotics and a very nosy environment. Hopefully this works properly.

## Sample 4

Audio: `recordings/2026-02-27/21-48-39/audio.wav`

### voxmlx:voxtral-mini-latest

- total_s: `29.57`
- first_token_s: `2.59`

Can we first do a bit more research on this? Like, for example, those MLX, allow for streaming or do we need specifically whisper streaming for it to work? And we're only talking about Whisper. Are there other options in currently? I mean, this

### faster:whisper-medium

- total_s: `18.90`
- first_token_s: `18.90`

Can we first do a bit more research on this?  For example, does MLX allow for streaming?  Or do we need, specifically, whisper streaming for it to work?  And we're only talking about whisper. Are there other options currently?  This seems to be a very rapidly moving subject.  I hear about a new model that does stuff.  I want you to research recent models that could be better than whisper for us.  Maybe that's not the case because you need to implement something specific for Apple for it to be better.  I need this research phase first.

### faster:whisper-small

- total_s: `6.58`
- first_token_s: `6.58`

Can we first do a bit more research on this?  For example, does MLX allow for streaming?  Or do we need specifically whisper streaming for it to work?  And we're only talking about whisper.  Are there other options currently?  This seems to be a very rapidly moving subject.  I hear about a new model that does recent models that are better than whisper for us.  Maybe that's not the case because you need to implement something specific for Apple for it to be better.  I need this research phase first.

### faster:whisper-base

- total_s: `2.30`
- first_token_s: `2.30`

Can we first do a bit more research on this?  Like, for example, does Ablelex allow for streaming?  Or do we need specifically whisper streaming for it to work?  And we're only talking about whisper.  Are there other options in currently?  I mean, this seems to be very rapidly moving subject type.  I've been here a week about a new model that I want you to research.  Recent models that are better than whisper for us.  Maybe that's not the case, because you need to implement something specific for Able  to be better.  But I need this research phase first.

## Sample 5

Audio: `recordings/2026-02-28/11-16-57/audio.wav`

### voxmlx:voxtral-mini-latest

- total_s: `17.00`
- first_token_s: `4.15`

Ok, donc je refais un message vocal en français. J'aimerais qu'on utilise celui-ci pour le

### faster:whisper-medium

- total_s: `18.17`
- first_token_s: `18.17`

Ok, donc je refais un message vocal en français.  J'aimerais qu'on utilise celui-ci pour le benchmark.  Je vais faire exprès d'utiliser des mots, des fois avec des longues pauses.  Je me demande si on peut poser des questions aussi.  Là, l'environnement est très silencieux.  Des fois, il y a des petits bruits de chaise, des trucs comme ça, mais grosso modo là,  c'est un contexte idéal.  Je pourrais peut-être travailler comme ça.  Et oui, je me demande si je peux utiliser du franglais, des mots un peu archotiques.  Tu vois, si je dis qu'est-ce que c'est que ce bordel de merde, est-ce que c'est bien traduit ?  Si je dis à la future, elle n'a pas été débatant, c'est de ma faute.  Tu vois, est-ce que ce genre de phrase fonctionne ?

### faster:whisper-small

- total_s: `6.66`
- first_token_s: `6.66`

Ok, donc je refais un message vocale en français.  J'aimerais que l'on utilise celui-ci pour le benchmark.  Je vais faire exploit d'utiliser des mots, des fois avec des longues pauses.  Je vais me demander si on peut poser des questions aussi.  Là, l'environnement est très silencieux.  Des fois, il y a des petits bruit de chaise, des trucs comme ça.  Mais pour ce modo, là, c'est un contexte idéal.  Je pourrais travailler comme ça.  Et oui, effectivement, si je peux utiliser du franglais, des mots un peu arcotiques,  tu vois, si je dis qu'est-ce que c'est que ce bordel de merde,  est-ce que c'est bien traduit,  si je dis que la feature, elle n'a pas été débattant, c'est de ma faute.  Tu vois, est-ce que ce genre de phrase fonctionne ?

### faster:whisper-base

- total_s: `3.26`
- first_token_s: `3.26`

Ok, donc je referais un message vocal en français, j'aimerais qu'on te souvienne pour le benchmark.  Je vais faire expliquer des mots, des fois avec des longues pauses.  Je pense que si on peut poser des questions,  la l'environnement est très silencieux pour des fois des petits branches,  mais pour ce modo, c'est un contexte idéal, je pourrais te travailler comme ça.  Et si je peux utiliser du franglais, des mots un peu arcotiques,  tu as 6 d'ici, qu'est-ce que c'est que ce bordel de merde,  ce que c'est bien traduit, si j'ai dit à la future,  à la paix de débatant, c'est de ma faute, tu as ce que ce genre de phrases fonctionne.

