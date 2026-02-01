# #!/bin/bash
# terminator -e "bash -c 'source /home/remi/.virtualenvs/whisper/bin/activate && cd /home/remi/voice2clipboard && python voice_transcriber.py; exec bash'"

#!/bin/bash
terminator -e "bash -c 'source /home/remi/.virtualenvs/whisper/bin/activate && cd /home/remi/voice2clipboard && python voice_transcriber.py; read -p \"✅ Press Enter to close...\"; exit'"

