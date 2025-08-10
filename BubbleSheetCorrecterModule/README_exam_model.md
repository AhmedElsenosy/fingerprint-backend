# Exam Model Bubble Collection Scripts

This set of scripts allows you to collect coordinates of exam model bubbles from bubble sheet images for later processing.

## Files Created

1. **`collect_exam_model_bubbles.py`** - Interactive GUI version (may have display issues in some environments)
2. **`collect_exam_model_manual.py`** - Command-line version that accepts coordinates
3. **`find_bubble_coordinates.py`** - Helper script to find coordinates interactively
4. **`exam_models.json`** - Output file containing saved exam model data
5. **`exam_model_visualization.jpg`** - Visual confirmation of detected bubbles

## How to Use

### Method 1: Manual Coordinates (Recommended)

If you know the approximate coordinates of 3 exam model bubbles:

```bash
python collect_exam_model_manual.py Arabic@4x-20.jpg "x1,y1 x2,y2 x3,y3"
```

Example:
```bash
python collect_exam_model_manual.py Arabic@4x-20.jpg "400,150 600,150 800,150"
```

### Method 2: Interactive Coordinate Finder

Use the helper script to find coordinates by clicking:

```bash
python find_bubble_coordinates.py Arabic@4x-20.jpg
```

This will:
- Display the image with ArUco markers highlighted
- Allow you to click on 3 bubble positions
- Print the command to run with those coordinates

### Method 3: GUI Version (May Cause Issues)

```bash
python collect_exam_model_bubbles.py Arabic@4x-20.jpg
```

## Output Format

The scripts save data to `exam_models.json` in this format:

```json
{
  "exam_model_1": {
    "aruco_markers": [
      {
        "id": 0,
        "corners": [[x1, y1], [x2, y2], [x3, y3], [x4, y4]]
      }
    ],
    "exam_model_bubbles": [
      {
        "model_letter": "A",
        "relative_center": [0.168, 0.045],
        "absolute_center": [400, 150],
        "circularity": 0.85,
        "area": 314.0
      }
    ],
    "image_size": {"width": 2382, "height": 3368},
    "source_image": "Arabic@4x-20.jpg",
    "timestamp": "2025-06-04T11:10:51.037250"
  }
}
```

## Key Features

1. **ArUco Marker Detection**: Automatically detects and stores ArUco marker positions for image alignment
2. **Bubble Detection**: Uses existing bubble detection algorithms to find precise contours near clicked positions
3. **Relative Coordinates**: Stores positions as both absolute pixels and relative (0-1) coordinates
4. **Visualization**: Creates a visual confirmation image showing detected bubbles and markers
5. **Multiple Models**: Supports storing multiple exam model configurations in the same file

## Usage in Bubble Processing Pipeline

Once you have collected exam model data, you can use it with the existing bubble processing scripts by:

1. Loading the exam model data from `exam_models.json`
2. Using the relative coordinates to find exam model bubbles in new images
3. Processing the exam model bubbles along with question and ID sections

## Troubleshooting

- **Segmentation Fault**: Use the manual coordinate version instead of the GUI
- **No Bubbles Detected**: The system will use your clicked positions even if no bubble contours are found
- **ArUco Markers Missing**: The system will still work but won't have perfect alignment reference
- **Wrong Coordinates**: Use the visualization image to verify bubble positions are correct

## Example Workflow

1. Find coordinates:
   ```bash
   python find_bubble_coordinates.py Arabic@4x-20.jpg
   ```

2. Collect model with found coordinates:
   ```bash
   python collect_exam_model_manual.py Arabic@4x-20.jpg "400,150 600,150 800,150"
   ```

3. Check the visualization:
   ```bash
   # View exam_model_visualization.jpg to confirm correct positioning
   ```

4. Use in your bubble processing pipeline:
   ```bash
   python compare_bubbles.py Arabic@4x-20.jpg --exam_model exam_models.json
   ``` 