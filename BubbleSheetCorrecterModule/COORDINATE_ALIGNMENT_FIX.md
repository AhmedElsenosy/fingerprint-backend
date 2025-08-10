# Exam Model Coordinate Alignment Fix

## 🎯 Issue Resolved

**Problem:** The exam model bubbles in the visualization were shifted to the right compared to their actual positions on the bubble sheet.

## 🔍 Root Cause Analysis

The issue was caused by a coordinate transformation mismatch:

1. **Collection Phase:** Exam model coordinates were collected on the **original image**
2. **Processing Phase:** The image gets **aligned/transformed** using ArUco markers via `cv2.warpAffine()`
3. **Visualization Phase:** Original coordinates were applied to the **transformed image**, causing position shift

### Technical Details

```python
# In compare_with_reference() function:
transform_matrix = cv2.getAffineTransform(cur_points[:3], ref_points[:3])
aligned_image = cv2.warpAffine(current_image, transform_matrix, (width, height))
```

The original exam model coordinates were being applied directly to the `aligned_image`, but they were collected relative to the untransformed image.

## ✅ Solution Implemented

Applied **inverse transformation** to exam model coordinates before processing:

### Code Changes in `compare_bubbles.py`

```python
# Added transform_matrix parameter to create_visualization()
def create_visualization(image, reference_data, id_reference_data=None, 
                        exam_model_data=None, transform_matrix=None):

    # For contour coordinates:
    if transform_matrix is not None:
        inv_transform = cv2.invertAffineTransform(transform_matrix)
        ones = np.ones((contour_points.shape[0], 1), dtype=np.float32)
        points_homogeneous = np.hstack([contour_points, ones])
        transformed_points = inv_transform.dot(points_homogeneous.T).T
        contour_points = transformed_points.astype(np.int32)

    # For center coordinates:
    if transform_matrix is not None:
        inv_transform = cv2.invertAffineTransform(transform_matrix)
        center_point = np.array([[center_x, center_y, 1]], dtype=np.float32)
        transformed_center = inv_transform.dot(center_point.T).T[0]
        center_x, center_y = int(transformed_center[0]), int(transformed_center[1])
```

### Updated Function Call

```python
# Pass transform matrix to visualization function
vis_image, grade_data = create_visualization(aligned_image, reference_data, 
                                           id_reference_data, exam_model_reference_data, transform)
```

## 🔧 How It Works

1. **Calculate Inverse Transform:** `cv2.invertAffineTransform(transform_matrix)`
2. **Transform Coordinates:** Apply inverse transformation to map coordinates from original image space to aligned image space
3. **Process Bubbles:** Use the corrected coordinates for bubble detection and visualization

## ✅ Results

- **✅ Accurate Positioning:** Exam model bubbles now appear at their correct positions
- **✅ Proper Alignment:** Coordinates align perfectly with ArUco-transformed image
- **✅ Maintained Functionality:** All existing features continue to work correctly
- **✅ Backward Compatibility:** Fix works with both new and old coordinate formats

## 🧪 Testing

The fix was validated with:

1. **Test Image Processing:** Created test images with filled exam model bubbles
2. **Visual Verification:** Confirmed bubbles appear at correct positions in output visualization
3. **Pipeline Integration:** Verified complete processing pipeline works correctly
4. **Multiple Formats:** Tested with both contour-based and center-based coordinates

## 📋 Files Modified

1. **`compare_bubbles.py`** - Updated `create_visualization()` function to apply coordinate transformation
2. **Test validation** - Confirmed fix resolves the positioning issue

## 🎉 Impact

This fix ensures that:

- Exam model bubbles are visualized at their **exact correct positions**
- The coordinate collection and processing pipeline is **fully aligned**
- Users can trust the **visual feedback** when reviewing bubble sheet results
- The system maintains **high accuracy** for exam model detection and grading 