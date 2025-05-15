#!/bin/bash

convert_file() {
    input_file="$1"
    output_file="${input_file%.mp3}.wav"
    echo "Converting: $input_file -> $output_file"
    ffmpeg -y -i "$input_file" "$output_file"
}

if [ -z "$1" ]; then
    echo "Usage: $0 <input_file_or_directory>"
    exit 1
fi

if [ -f "$1" ]; then
    # Single file
    if [[ "$1" == *.mp3 ]]; then
        convert_file "$1"
    else
        echo "Error: Provided file is not an .mp3 file."
    fi
elif [ -d "$1" ]; then
    # Directory
    find "$1" -type f -name "*.mp3" | while read -r file; do
        convert_file "$file"
    done
else
    echo "Error: $1 is not a valid file or directory."
    exit 1
fi
