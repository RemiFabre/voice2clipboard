#!/bin/bash

# Array to store successfully created files
created_files=()
# Counter for conversion errors
conversion_errors=0

convert_file() {
    local input_file="$1" # Use local for function variables
    local output_file="${input_file%.mp3}.wav"

    echo "Converting: $input_file -> $output_file"

    if ffmpeg -nostdin -y -i "$input_file" "$output_file" -loglevel error; then
        created_files+=("$output_file")
        return 0 # Success
    else
        echo "ERROR: Failed to convert '$input_file'." >&2 # Send errors to stderr
        ((conversion_errors++))
        return 1 # Failure
    fi
}

if [ -z "$1" ]; then
    echo "Usage: $0 <input_file_or_directory>"
    exit 1
fi

input_path="$1"

if [ -f "$input_path" ]; then
    # Single file
    if [[ "$input_path" == *.mp3 ]]; then
        convert_file "$input_path"
    else
        echo "Error: Provided file '$input_path' is not an .mp3 file." >&2
        exit 1
    fi
elif [ -d "$input_path" ]; then
    # Directory (non-recursive)
    echo "Processing .mp3 files in directory: $input_path"

    # Normalize the path for globbing to prevent double slashes (e.g., dir//file.mp3)
    # by removing a single trailing slash if it exists.
    # If input_path is "/", this results in an empty string, and "/*.mp3" is correctly used by the glob.
    glob_base="${input_path%/}" # <--- REMOVED 'local' from here

    shopt -s nullglob
    # If glob_base is empty (e.g., input_path was "/"), then "$glob_base/*.mp3" becomes "/*.mp3"
    # If glob_base is "dir", then it becomes "dir/*.mp3"
    mp3_files_in_dir=("$glob_base"/*.mp3)
    shopt -u nullglob # Reset nullglob to default behavior

    if [ ${#mp3_files_in_dir[@]} -eq 0 ]; then
        echo "No .mp3 files found in '$input_path'."
    else
        for file in "${mp3_files_in_dir[@]}"; do
            # $file will now have a clean path like "dir/file.mp3" or "/file.mp3"
            if [ -f "$file" ]; then
                convert_file "$file"
            fi
        done
    fi
else
    echo "Error: '$input_path' is not a valid file or directory." >&2
    exit 1
fi

echo # Add a newline for better separation before the summary

# Summary of operations
if [ ${#created_files[@]} -gt 0 ]; then
    echo -e "\n--- Conversion Summary ---"
    echo "Successfully created the following .wav files:"
    for f_created in "${created_files[@]}"; do
        echo "  - $f_created" # This will now print the cleaned path
    done
else
    if [ "$conversion_errors" -eq 0 ]; then
        # This case means no MP3s were found or the input was not an MP3 file (already handled)
        echo "No .mp3 files were processed or found to convert."
    fi
fi

if [ "$conversion_errors" -gt 0 ]; then
    echo -e "\nWarning: $conversion_errors MP3 file(s) failed to convert."
    echo "Script finished with errors."
    exit 1
else
    if [ ${#created_files[@]} -gt 0 ]; then
        echo -e "\nAll targeted MP3 conversions completed successfully!"
    fi
    echo "Script finished."
    exit 0
fi