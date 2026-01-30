#!/bin/bash

# Convert audio files (mp3, ogg, m4a, flac, opus) to WAV format
# Supports single files or directories

SUPPORTED_EXTENSIONS="mp3 ogg m4a flac opus"

created_files=()
conversion_errors=0

convert_file() {
    local input_file="$1"
    local base="${input_file%.*}"
    local output_file="${base}.wav"

    echo "Converting: $input_file -> $output_file"

    if ffmpeg -nostdin -y -i "$input_file" "$output_file" -loglevel error; then
        created_files+=("$output_file")
        return 0
    else
        echo "ERROR: Failed to convert '$input_file'." >&2
        ((conversion_errors++))
        return 1
    fi
}

is_supported_extension() {
    local file="$1"
    local ext="${file##*.}"
    ext="${ext,,}" # lowercase
    for supported in $SUPPORTED_EXTENSIONS; do
        if [[ "$ext" == "$supported" ]]; then
            return 0
        fi
    done
    return 1
}

if [ -z "$1" ]; then
    echo "Usage: $0 <input_file_or_directory>"
    echo ""
    echo "Converts audio files to WAV format using ffmpeg."
    echo "Supported formats: $SUPPORTED_EXTENSIONS"
    echo ""
    echo "Examples:"
    echo "  $0 voice_message.ogg      # Convert single file"
    echo "  $0 ~/Downloads/           # Convert all audio files in directory"
    exit 1
fi

input_path="$1"

if [ -f "$input_path" ]; then
    if is_supported_extension "$input_path"; then
        convert_file "$input_path"
    else
        echo "Error: '$input_path' is not a supported audio format." >&2
        echo "Supported: $SUPPORTED_EXTENSIONS" >&2
        exit 1
    fi
elif [ -d "$input_path" ]; then
    echo "Processing audio files in directory: $input_path"

    glob_base="${input_path%/}"
    found_files=0

    shopt -s nullglob
    for ext in $SUPPORTED_EXTENSIONS; do
        for file in "$glob_base"/*."$ext"; do
            if [ -f "$file" ]; then
                convert_file "$file"
                ((found_files++))
            fi
        done
    done
    shopt -u nullglob

    if [ "$found_files" -eq 0 ]; then
        echo "No supported audio files found in '$input_path'."
        echo "Supported: $SUPPORTED_EXTENSIONS"
    fi
else
    echo "Error: '$input_path' is not a valid file or directory." >&2
    exit 1
fi

echo

if [ ${#created_files[@]} -gt 0 ]; then
    echo -e "\n--- Conversion Summary ---"
    echo "Successfully created:"
    for f_created in "${created_files[@]}"; do
        echo "  - $f_created"
    done
fi

if [ "$conversion_errors" -gt 0 ]; then
    echo -e "\nWarning: $conversion_errors file(s) failed to convert."
    exit 1
else
    if [ ${#created_files[@]} -gt 0 ]; then
        echo -e "\nAll conversions completed successfully!"
    fi
    exit 0
fi
