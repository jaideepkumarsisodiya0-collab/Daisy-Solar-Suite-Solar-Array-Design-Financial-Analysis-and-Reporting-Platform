from fpdf import FPDF
import io
import datetime

class DaisyPDFReport(FPDF):
    def header(self):
        # We only want the standard header on pages after the cover page
        if self.page_no() > 1:
            self.set_font('Helvetica', 'B', 20)
            self.set_text_color(30, 58, 138) # Dark Blue
            self.cell(0, 10, 'Daisy.', 0, 1, 'L')
            self.set_font('Helvetica', 'I', 10)
            self.set_text_color(100, 116, 139) # Gray
            self.cell(0, 5, 'Issued For Construction & Financial Feasibility Report', 0, 1, 'L')
            self.ln(10)

    def footer(self):
        if self.page_no() > 1:
            self.set_y(-15)
            self.set_font('Helvetica', 'I', 8)
            self.set_text_color(150, 150, 150)
            self.cell(0, 10, f'Page {self.page_no() - 1}', 0, 0, 'C')

    def chapter_title(self, num, title):
        self.set_font('Helvetica', 'B', 16)
        self.set_text_color(30, 58, 138)
        self.set_fill_color(241, 245, 249)
        self.cell(0, 10, f'{num}. {title}', 0, 1, 'L', 1)
        self.ln(4)

    def chapter_body(self, text):
        self.set_font('Helvetica', '', 11)
        self.set_text_color(50, 50, 50)
        self.multi_cell(0, 6, text)
        self.ln(4)

def generate_pdf_report(data):
    pdf = DaisyPDFReport()
    
    # ---------------------------------------------------------
    # COVER PAGE
    # ---------------------------------------------------------
    pdf.add_page()
    # Beige Background
    pdf.set_fill_color(247, 245, 240)
    pdf.rect(0, 0, 210, 297, 'F')
    
    pdf.ln(80)
    pdf.set_font('Helvetica', 'B', 48)
    pdf.set_text_color(30, 58, 138)
    pdf.cell(0, 20, "Daisy.", 0, 1, 'C')
    
    pdf.ln(10)
    pdf.set_font('Helvetica', '', 16)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(0, 10, "Issued For Construction & Financial Feasibility", 0, 1, 'C')
    
    pdf.ln(20)
    pdf.set_font('Helvetica', '', 12)
    pdf.set_text_color(71, 85, 105)
    pdf.cell(0, 8, f"Project Location: {data.get('location', 'Unknown')}", 0, 1, 'C')
    pdf.cell(0, 8, f"Date: {datetime.datetime.now().strftime('%B %d, %Y')}", 0, 1, 'C')
    
    # Daisy Logo at bottom right
    pdf.set_y(-30)
    pdf.set_x(-40)
    pdf.set_font('Helvetica', 'B', 24)
    pdf.set_text_color(30, 58, 138)
    pdf.cell(30, 10, "Daisy.", 0, 0, 'R')
    
    # ---------------------------------------------------------
    # 1.0 Executive Summary
    # ---------------------------------------------------------
    pdf.add_page()
    pdf.chapter_title(1, "Executive Summary")
    intro_text = (
        f"This comprehensive engineering report outlines the technical and financial feasibility "
        f"of the proposed hybrid energy system.\n\n"
        f"Site Details:\n"
        f"Location: {data.get('location', 'N/A')}\n"
        f"Coordinates: {data.get('lat', 0):.4f} deg Lat, {data.get('lon', 0):.4f} deg Lon\n\n"
        f"System Size:\n"
        f"DC Capacity: {data.get('total_kw', 0):,.1f} kWp\n"
        f"AC Capacity: {data.get('inv_ac_kw', 0):,.1f} kW\n\n"
        f"Bottom Line Economics:\n"
        f"Total Net Cost: INR {data.get('net_cost', 0):,.0f}\n"
        f"Estimated Payback: {data.get('payback_yr', 'N/A')} Years\n"
        f"Levelized Cost of Energy (LCOE): INR {data.get('lcoe', 0):.2f} / kWh\n"
    )
    pdf.chapter_body(intro_text)
    
    # ---------------------------------------------------------
    # 2.0 Site & Load Analysis
    # ---------------------------------------------------------
    pdf.chapter_title(2, "Site & Load Analysis")
    site_text = (
        f"Available vs. Usable Roof Area:\n"
        f"Total Site/Roof Area: {data.get('total_roof_area', 0):,.1f} sq.m\n"
        f"Usable Area (Array Footprint): {data.get('usable_roof_area', 0):,.1f} sq.m\n\n"
        f"Energy Consumption Profile:\n"
        f"Target Daily Generation / Demand: {data.get('target_gen_kwh', 0):.1f} kWh/day\n"
    )
    pdf.chapter_body(site_text)

    # ---------------------------------------------------------
    # 3.0 System Architecture & Sizing
    # ---------------------------------------------------------
    pdf.chapter_title(3, "System Architecture & Sizing")
    phase_str = "3-Phase" if data.get('inv_ac_kw', 0) >= 10 else "1-Phase"
    batt_str = f"Energy Storage: {data.get('batt_cap', 0):.1f} kWh Usable ({data.get('batt_model', '')})\n" if data.get('batt_cap', 0) > 0 else ""
    arch_text = (
        f"DC Subsystem:\n"
        f"Module Specifications: {data.get('panel_model', 'N/A')}\n"
        f"Total Module Count: {data.get('panel_count', 0)} units\n"
        f"String Configuration: {data.get('num_parallel_strings', 0)} strings of {data.get('modules_in_series', 0)} modules.\n"
        f"{batt_str}\n"
        f"AC Subsystem:\n"
        f"Inverter Specifications: {data.get('num_inverters', 1)}x {data.get('inverter_model', 'N/A')}\n"
        f"Total AC Capacity: {data.get('inv_ac_kw', 0):,.1f} kW\n"
        f"Phase Connection: {phase_str}\n"
        f"DC/AC Ratio: {data.get('dc_ac_ratio', 0):.2f}\n\n"
        f"Mechanical / Civil:\n"
        f"Mounting Type: {data.get('mount_type', 'N/A')}\n"
        f"Array Azimuth: {data.get('azimuth', 0)} deg\n"
        f"Seasonal Tilt Angle: {data.get('tilt', 0)} deg\n"
        f"Inter-Row Spacing: {data.get('row_gap', 0):.2f} m\n"
    )
    pdf.chapter_body(arch_text)
    
    # ---------------------------------------------------------
    # 4.0 Yield Simulation & Environmental Data
    # ---------------------------------------------------------
    pdf.add_page()
    pdf.chapter_title(4, "Yield Simulation & Environmental Data")
    env_text = (
        f"Historical Irradiance Data (NASA POWER Satellite):\n"
        f"Annual Global Horizontal Irradiance (GHI): {data.get('annual_rad', 0):.2f} kWh/sq.m/day\n\n"
        f"System Losses:\n"
        f"Thermal Degradation (Heat Loss): {data.get('thermal_derate_pct', 0):.2f}%\n"
        f"Soiling (Dust/Snow) Loss: {data.get('soiling_loss', 0):.2f}%\n"
        f"Light Induced Degradation (LID): {data.get('lid_loss', 0):.2f}%\n"
    )
    pdf.chapter_body(env_text)
    
    if data.get('power_image'):
        pdf.image(data['power_image'], x=15, w=180)
        pdf.ln(5)
        
    if data.get('nasa_image'):
        pdf.image(data['nasa_image'], x=15, w=180)
        pdf.ln(5)
        
    # ---------------------------------------------------------
    # 5.0 Advanced Subsystems (Thermal & Backup)
    # ---------------------------------------------------------
    if data.get('th_active') or data.get('generator_kw', 0) > 0:
        pdf.add_page()
        pdf.chapter_title(5, "Advanced Subsystems (Thermal & Backup Generator)")
        sub_text = ""
        if data.get('th_active'):
            sub_text += (
                f"Solar Thermal Engine:\n"
                f"Target Daily Output: {data.get('target_lpd', 0):.1f} LPD\n"
                f"Thermal Input Delta (T_out - T_in): {data.get('delta_t', 0):.1f} °C\n"
                f"Equivalent Thermal Yield: {data.get('daily_thermal_energy_kwh', 0):.2f} kWh/day\n"
                f"Collector Array: {data.get('thermal_panels', 0)} Panels\n\n"
            )
        if data.get('generator_kw', 0) > 0:
            sub_text += (
                f"Backup Generator Set:\n"
                f"Required Capacity: {data.get('generator_kw', 0):.1f} kVA\n"
                f"Fuel Run Hours: {data.get('fuel_run_hours', 0):.1f} hours/day\n\n"
            )
        pdf.chapter_body(sub_text)

    # ---------------------------------------------------------
    # 6.0 Financial Feasibility
    # ---------------------------------------------------------
    pdf.add_page()
    pdf.chapter_title(6, "Financial Feasibility & Cash Flows")
    
    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(90, 8, 'Metric', 1)
    pdf.cell(90, 8, 'Value', 1, 1)
    
    pdf.set_font('Helvetica', '', 11)
    metrics = [
        ("Gross CAPEX Cost", f"INR {data.get('gross_cost', 0):,.0f}"),
        ("Net CAPEX (After Subsidies)", f"INR {data.get('net_cost', 0):,.0f}"),
        ("First Year Savings/Revenue", f"INR {data.get('pv_savings', 0):,.0f}"),
        ("Estimated Payback Period", f"{data.get('payback_yr')} Years" if data.get('payback_yr') else "No Breakeven"),
        ("Levelized Cost of Energy (LCOE)", f"INR {data.get('lcoe', 0):.2f} / kWh"),
        ("25-Year Cumulative Cash Flow", f"INR {data.get('cumulative_profit', 0):,.0f}")
    ]
    for k, v in metrics:
        pdf.cell(90, 8, k, 1)
        pdf.cell(90, 8, v, 1, 1)
    pdf.ln(5)
    
    if data.get('cf_image'):
        pdf.image(data['cf_image'], x=15, w=180)
        pdf.ln(5)

    if data.get('bom_image'):
        pdf.image(data['bom_image'], x=30, w=150)
        pdf.ln(5)

    # ---------------------------------------------------------
    # 7.0 ASCE-7 Structural Analysis
    # ---------------------------------------------------------
    pdf.add_page()
    pdf.chapter_title(7, "ASCE-7 Structural Analysis")
    
    dead_load = data.get('dead_load', 0)
    wind_uplift = data.get('wind_uplift', 0)
    snow_load = data.get('snow_load', 0)
    total_combined = data.get('total_combined_load', 0)
    roof_capacity = data.get('roof_capacity', 0)
    struct_status = "Structurally Safe" if total_combined <= roof_capacity else f"Overload: Exceeds {roof_capacity} kg/sq.m"
    
    struct_text = (
        f"Dead Load (Panels + Mounting Hardware): {dead_load:.2f} kg/sq.m\n"
        f"Wind Uplift Load (Live Aerodynamic Force): {wind_uplift:.2f} kg/sq.m\n"
        f"Live Snow Load: {snow_load:.2f} kg/sq.m\n\n"
        f"Total Combined Load: {total_combined:.2f} kg/sq.m\n"
        f"Structural Assessment: {struct_status}\n\n"
    )
    if total_combined > roof_capacity:
        struct_text += "WARNING: Structural reinforcement is required prior to installation.\n"
    pdf.chapter_body(struct_text)

    # ---------------------------------------------------------
    # 8.0 Engineering Diagrams (CAD & SLD)
    # ---------------------------------------------------------
    pdf.add_page()
    pdf.chapter_title(8, "Engineering Diagrams")
    if data.get('cad_image'):
        pdf.set_font('Helvetica', 'B', 12)
        pdf.cell(0, 10, "Issued For Construction (IFC) Floorplan:", 0, 1)
        pdf.image(data['cad_image'], x=15, w=180)
        pdf.ln(5)
        
    if data.get('sld_image'):
        pdf.add_page()
        pdf.set_font('Helvetica', 'B', 12)
        pdf.cell(0, 10, "Electrical System Architecture (Block Diagram):", 0, 1)
        pdf.image(data['sld_image'], x=15, w=180)
        pdf.ln(5)
        
    if data.get('true_sld_image'):
        pdf.add_page()
        pdf.set_font('Helvetica', 'B', 12)
        pdf.cell(0, 10, "Technical Single-Line Diagram (ANSI/IEC Standard):", 0, 1)
        pdf.image(data['true_sld_image'], x=15, w=180)
        pdf.ln(5)

    # ---------------------------------------------------------
    # 9.0 Conclusion
    # ---------------------------------------------------------
    pdf.add_page()
    pdf.chapter_title(9, "Conclusion")
    if data.get('payback_yr') and data.get('payback_yr') < 10:
        conclusion = "Highly Feasible: Excellent return on investment with a rapid payback period. Proceeding to execution is strongly recommended."
    elif data.get('payback_yr') and data.get('payback_yr') < 25:
        conclusion = "Feasible: Project breaks even within lifespan and generates net positive profit."
    else:
        conclusion = "Marginal Feasibility: Adjust load profiles or utilize different hardware."
    pdf.chapter_body(conclusion)
    
    return bytes(pdf.output(dest='S'))
