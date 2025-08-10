# Bubble Sheet Reader

This Python script processes bubble sheet (OMR) answer sheets and extracts the marked answers into a CSV file.

## Features

- Process single or multiple bubble sheet images
- Automatic sheet detection and perspective correction
- Extracts marked answers from bubble grids
- Outputs results in CSV format
- Handles multiple choice answers (A-E)

## Requirements

- Python 3.7+
- OpenCV
- NumPy
- Pandas
- imutils

## Installation

1. Clone this repository or download the files
2. Install the required packages:

```bash
pip install -r requirements.txt
```

## Usage

### Processing a Single Image

1. Place your bubble sheet image in the same directory as the script
2. Update the `image_path` variable in `main()` to point to your image
3. Run the script:

```bash
python bubble_sheet_reader.py
```

### Processing Multiple Images

1. Create a directory containing all your bubble sheet images
2. Uncomment the directory processing code in `main()`
3. Update the `directory_path` variable to point to your images directory
4. Run the script as above

## Output

The script will create a `results.csv` file containing:
- Image filename
- Question numbers as columns
- Marked answers (A-E) for each question

## Troubleshooting

If the script fails to detect answers correctly, try:
1. Ensure the image is well-lit and high contrast
2. Check that the image is not too skewed
3. Verify that the bubbles are clearly marked
4. Make sure the image is in focus and not blurry

## Notes

- The script expects bubble sheets with a similar format to the provided template
- Supported image formats: JPG, PNG
- The script automatically handles perspective correction for slightly skewed images
- For best results, ensure good lighting and clear bubble markings 