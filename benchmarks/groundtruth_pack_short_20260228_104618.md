# Ground Truth Curation Pack

- Source manifest: `benchmarks/manifest_groundtruth_seed_short.jsonl`
- JSON bundle: `benchmarks/groundtruth_pack_short_20260228_104618.json`
- Annotation template: `benchmarks/groundtruth_pack_short_20260228_104618_annotations.jsonl`
- Editable matrix CSV: `benchmarks/groundtruth_pack_short_20260228_104618_matrix.csv`

For each sample, choose the best candidate and manually correct into annotation template.

## Sample 1

Audio: `recordings/2026-02-27/16-10-29/audio.wav`

### voxmlx:voxtral-mini-latest

- total_s: `12.18`
- first_token_s: `0.93`

Hey, just

### faster:whisper-medium

- total_s: `9.12`
- first_token_s: `9.12`

Hey, just testing if this works, hopefully it does.

### faster:whisper-small

- total_s: `3.55`
- first_token_s: `3.55`

Hey just testing if this works hopefully it does

### faster:whisper-base

- total_s: `1.75`
- first_token_s: `1.75`

Hey just testing if this works hopefully it does

## Sample 2

Audio: `recordings/2026-02-27/17-09-26/audio.wav`

### voxmlx:voxtral-mini-latest

- total_s: `12.28`
- first_token_s: `1.05`

Okay

### faster:whisper-medium

- total_s: `9.97`
- first_token_s: `9.97`

Ok, testing if this transcript works and if it's fast enough.  There is some noise around, so let's see if the transcription is good.  My sentences should be normal, so if you see weird words or stuff like that, that shouldn't make sense.  It's probably transcription mistakes, but that's another problem.

### faster:whisper-small

- total_s: `3.47`
- first_token_s: `3.47`

Ok, testing if this transcript works and if it's fast enough, there's some noise around.  So let's see if the transcription is good.  My sentence should be normal, so if you see weird words or stuff like that, that shouldn't make sense.  It's probably transcription mistakes, but that's another problem.

### faster:whisper-base

- total_s: `1.38`
- first_token_s: `1.38`

Okay, testing if this transcript works.  It's fast enough.  There's some noise around.  So, I'll receive the transcription.  It's good.  My sentence should be normal.  So, if you see weird words or stuff like that, that shouldn't make sense.  It's probably transcription mistakes, but that's another problem.

## Sample 3

Audio: `recordings/2026-02-27/18-17-10/audio.wav`

### voxmlx:voxtral-mini-latest

- total_s: `14.03`
- first_token_s: `2.80`

Okay, I

### faster:whisper-medium

- total_s: `9.85`
- first_token_s: `9.85`

Okay, I'm trying again. Let's see if this time the transcription is correct.  I'm doing a bit of a long message. Let's assume this is a message of like, I don't know, maybe 15 seconds.  This causes inverse kinematics in robotics in a very nosy environment. Hopefully this works properly.

### faster:whisper-small

- total_s: `3.51`
- first_token_s: `3.51`

Okay, I'm trying again. Let's see if this time the transcription is correct. I'm doing a bit of a long message  Let's assume this is a message of like, I don't know, maybe 15 seconds. This causes inverse kinematics in robotics and in a very noisy environment  Hopefully this works properly

### faster:whisper-base

- total_s: `1.61`
- first_token_s: `1.61`

Okay, I'm trying again. Let's see if this time the transcription is correct. I'm doing a bit of a long message. Let's assume this message of like 15 seconds.  This causes the inverse kinematics in robotics and a very nosy environment. Hopefully this works properly.

## Sample 4

Audio: `recordings/2026-02-27/21-48-39/audio.wav`

### voxmlx:voxtral-mini-latest

- total_s: `27.83`
- first_token_s: `2.36`

Can we first do a bit more research on this? Like, for example, those MLX, allow for streaming or do we need specifically whisper streaming for it to work? And we're only talking about Whisper. Are there other options

### faster:whisper-medium

- total_s: `19.07`
- first_token_s: `19.07`

Can we first do a bit more research on this?  For example, does MLX allow for streaming?  Or do we need, specifically, whisper streaming for it to work?  And we're only talking about whisper. Are there other options currently?  This seems to be a very rapidly moving subject.  I hear about a new model that does stuff.  I want you to research recent models that could be better than whisper for us.  Maybe that's not the case because you need to implement something specific for Apple for it to be better.  I need this research phase first.

### faster:whisper-small

- total_s: `6.29`
- first_token_s: `6.29`

Can we first do a bit more research on this?  For example, does MLX allow for streaming?  Or do we need specifically whisper streaming for it to work?  And we're only talking about whisper.  Are there other options currently?  This seems to be a very rapidly moving subject.  I hear about a new model that does recent models that are better than whisper for us.  Maybe that's not the case because you need to implement something specific for Apple for it to be better.  I need this research phase first.

### faster:whisper-base

- total_s: `2.31`
- first_token_s: `2.31`

Can we first do a bit more research on this?  Like, for example, does Ablelex allow for streaming?  Or do we need specifically whisper streaming for it to work?  And we're only talking about whisper.  Are there other options in currently?  I mean, this seems to be very rapidly moving subject type.  I've been here a week about a new model that I want you to research.  Recent models that are better than whisper for us.  Maybe that's not the case, because you need to implement something specific for Able  to be better.  But I need this research phase first.

