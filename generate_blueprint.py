from PIL import Image, ImageDraw, ImageFont

# 1. Create a blank white canvas (representing a 30m x 20m scaled ratio)
width, height = 900, 600
img = Image.new('RGB', (width, height), color='white')
draw = ImageDraw.Draw(img)

# 2. Draw the Main Roof Structure (Light Grey)
draw.rectangle([50, 50, 850, 550], fill='#e0e0e0', outline='black', width=4)

# 3. Add an HVAC / Air Conditioning Unit obstacle (Dark Grey)
draw.rectangle([650, 100, 800, 200], fill='#808080', outline='black', width=2)
draw.text((690, 140), "HVAC UNIT", fill="white")

# 4. Add a Skylight obstacle (Light Blue)
draw.rectangle([150, 400, 300, 500], fill='#add8e6', outline='black', width=2)
draw.text((190, 440), "SKYLIGHT", fill="black")

# 5. Add Architectural Dimension Labels
draw.text((400, 20), "ROOF WIDTH: 30 METERS (X-AXIS)", fill="black")
draw.text((10, 280), "20 METERS (Y)", fill="black")

# 6. Save the image to your folder
img.save('sample_roof_plan.png')
print("✅ sample_roof_plan.png has been generated successfully!")