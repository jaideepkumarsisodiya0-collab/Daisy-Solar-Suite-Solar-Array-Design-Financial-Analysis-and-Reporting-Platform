from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import ezdxf
import io
import json
import os

app = FastAPI()

# Allow React to talk to Python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_methods=["*"],
    allow_headers=["*"],
)

# Host the built React CAD App as static files
if os.path.exists("cad_build"):
    app.mount("/cad", StaticFiles(directory="cad_build", html=True), name="cad")

@app.post("/save-cad")
async def save_cad(data: dict):
    with open("cad_data.json", "w") as f:
        json.dump(data, f)
    return {"status": "success"}

class CADData(BaseModel):
    shapes: list

@app.post("/export-dxf")
async def export_dxf(data: CADData):
    # 1. Create a new DXF document
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()

    # 2. Iterate through the React JSON and map to DXF entities
    for shape in data.shapes:
        if shape.get("type") == "line" or shape.get("type") == "polyline":
            pts = shape.get("points")
            for i in range(0, len(pts)-2, 2):
                msp.add_line((pts[i], pts[i+1]), (pts[i+2], pts[i+3]))
                
        elif shape.get("type") == "rect":
            x, y, w, h = shape.get("x"), shape.get("y"), shape.get("w"), shape.get("h")
            msp.add_lwpolyline([(x, y), (x+w, y), (x+w, y+h), (x, y+h), (x, y)], close=True)
            
        elif shape.get("type") == "circle":
            msp.add_circle((shape.get("x"), shape.get("y")), shape.get("radius"))

    # 3. Save to memory and return as a downloadable file
    mem_buffer = io.StringIO()
    doc.write(mem_buffer)
    
    return Response(
        content=mem_buffer.getvalue(), 
        media_type="application/dxf",
        headers={"Content-Disposition": "attachment; filename=Daisy_Export.dxf"}
    )

# Run this server using: uvicorn cad_api:app --reload --port 8000