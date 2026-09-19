import cv2
import numpy as np

def create_base_canvas(width=1200, height=800):
    """Creates a clean white canvas with a standard blueprint outer boundary line."""
    # White background
    canvas = np.ones((height, width, 3), dtype=np.uint8) * 255
    # Thin outer black border (simulating layout edges)
    cv2.rectangle(canvas, (10, 10), (width - 10, height - 10), (0, 0, 0), 2)
    return canvas

def generate_test_suite():
    print("Generating synthetic solar layout test suite...")

    # =========================================================================
    # TEST LAYOUT 1: Standard Commercial Roof (Verification Plan)
    # Target: Verifies basic Canny edge capture and clean panel wrapping around macro structures.
    # =========================================================================
    plan_1 = create_base_canvas()
    # Large Central HVAC Unit
    cv2.rectangle(plan_1, (400, 250), (600, 450), (60, 60, 60), 3)
    cv2.putText(plan_1, "HVAC-MAIN", (430, 350), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)
    
    # Secondary Skylight
    cv2.rectangle(plan_1, (850, 150), (1000, 300), (100, 100, 100), 3)
    cv2.putText(plan_1, "SKYLIGHT 01", (860, 220), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
    
    cv2.imwrite("roof_test_1_standard.png", plan_1)
    print(" -> Saved: roof_test_1_standard.png")


    # =========================================================================
    # TEST LAYOUT 2: Congested High-Density Plan (Stress Test)
    # Target: Verifies if the AABB packing algorithm manages tight clearance spaces between blocks.
    # =========================================================================
    plan_2 = create_base_canvas()
    
    # Array of small mechanical exhaust vents (6 structured obstructions)
    vent_coords = [
        ((200, 150), (280, 230)),
        ((200, 350), (280, 430)),
        ((200, 550), (280, 630)),
        ((550, 150), (630, 230)),
        ((550, 550), (630, 630)),
    ]
    for start, end in vent_coords:
        cv2.rectangle(plan_2, start, end, (50, 50, 50), 3)
        
    # Long rectangular pipe/tray line route across the right sector
    cv2.rectangle(plan_2, (800, 100), (860, 700), (80, 80, 80), 3)
    cv2.putText(plan_2, "CABLE TRAY ZONE", (805, 400), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 1)

    cv2.imwrite("roof_test_2_congested.png", plan_2)
    print(" -> Saved: roof_test_2_congested.png")


    # =========================================================================
    # TEST LAYOUT 3: Edge Case / Text Noise Plan (Validation Matrix)
    # Target: Validates the V27.0 changes. Checks if text or massive border blocks crash the layout.
    # =========================================================================
    plan_3 = create_base_canvas()
    
    # Scattered floating text labels (Low geometric area - should be skipped by filter)
    cv2.putText(plan_3, "ROOF SLOPE: 2 DEGREES", (100, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
    cv2.putText(plan_3, "NORTH INDICATOR V1", (950, 750), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)
    
    # Concentric/Overlapping structural squares (Tests the new spatial De-Duplication filter)
    cv2.rectangle(plan_3, (450, 300), (650, 500), (30, 30, 30), 4)
    cv2.rectangle(plan_3, (455, 305), (645, 495), (150, 150, 150), 2) # Inner duplicate line
    cv2.putText(plan_3, "MAINTENANCE PUMP", (465, 400), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
    
    # An obstacle placed tightly against the boundary line
    cv2.rectangle(plan_3, (12, 300), (120, 500), (0, 0, 0), 3)
    cv2.putText(plan_3, "INVERTER SHED", (15, 400), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 1)

    cv2.imwrite("roof_test_3_noise_test.png", plan_3)
    print(" -> Saved: roof_test_3_noise_test.png")
    print("\nInitialization Complete. Upload these files into your Streamlit App dashboard.")

if __name__ == "__main__":
    generate_test_suite()