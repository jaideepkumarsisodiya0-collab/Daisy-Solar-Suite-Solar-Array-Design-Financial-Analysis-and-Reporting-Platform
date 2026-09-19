# Solar Feasibility Calculator - Version 2.0
# Added: Branching logic for PV vs. Thermal

print("--- Solar Feasibility Calculator ---")
print("Which system do you want to design?")
print("1. Solar PV (For Electricity)")
print("2. Solar Thermal (For Hot Water)")

# The 'input' command grabs the user's choice as text
system_choice = input("Enter 1 or 2: ")

# --- PIPELINE 1: SOLAR PV ---
if system_choice == '1':
    print("\n--- Solar PV Sizing ---")
    available_area = float(input("Enter available roof/ground area (in sq meters): "))
    monthly_bill = float(input("Enter average monthly electricity bill: "))

    PANEL_AREA_SQM = 2.0
    PANEL_POWER_KW = 0.5
    LAYOUT_EFFICIENCY = 0.8
    KWH_PER_KWP_PER_DAY = 4.0
    TARIFF = 8.0
    INSTALL_COST_PER_KW = 60000

    max_panels_possible = (available_area / PANEL_AREA_SQM) * LAYOUT_EFFICIENCY
    max_kw_from_space = max_panels_possible * PANEL_POWER_KW

    monthly_consumption_kwh = monthly_bill / TARIFF
    required_kw_from_load = monthly_consumption_kwh / (30 * KWH_PER_KWP_PER_DAY)

    recommended_system_kw = min(max_kw_from_space, required_kw_from_load)
    total_panels_needed = recommended_system_kw / PANEL_POWER_KW

    total_cost = recommended_system_kw * INSTALL_COST_PER_KW
    annual_generation_kwh = recommended_system_kw * KWH_PER_KWP_PER_DAY * 365
    annual_savings = annual_generation_kwh * TARIFF

    if annual_savings > 0:
        payback_period = total_cost / annual_savings
    else:
        payback_period = 0

    print("\n--- PV System Results ---")
    print(f"Recommended System Size: {recommended_system_kw:.2f} kW")
    print(f"Total Panels Required: {int(total_panels_needed)} panels")
    print(f"Total Cost: {total_cost:,.2f}")
    print(f"Annual Savings: {annual_savings:,.2f}")
    print(f"Payback Period: {payback_period:.2f} years")

# --- PIPELINE 2: SOLAR THERMAL ---
elif system_choice == '2':
    print("\n--- Solar Thermal Sizing ---")
    available_area = float(input("Enter available roof/ground area (in sq meters): "))
    daily_hot_water = float(input("Enter daily hot water requirement (in Liters): "))

    # Constants for Thermal (Assuming Evacuated Tube or Flat Plate)
    COLLECTOR_AREA_SQM = 2.0      # Area of one standard thermal collector
    LPD_PER_COLLECTOR = 100.0     # Liters Per Day one collector can heat
    LAYOUT_EFFICIENCY = 0.8
    COST_PER_100_LPD = 25000      # Approx capital cost per 100 LPD
    TARIFF = 8.0                  # Electricity cost per unit

    # Energy calculations: Heating 100L water by ~40 deg C takes ~4.65 kWh of energy
    KWH_SAVED_PER_100L = 4.65

    # Step A: Space constraint
    max_collectors = (available_area / COLLECTOR_AREA_SQM) * LAYOUT_EFFICIENCY
    max_lpd_from_space = max_collectors * LPD_PER_COLLECTOR

    # Step B: Optimization based on space vs requirement
    recommended_lpd = min(max_lpd_from_space, daily_hot_water)
    final_collectors_needed = recommended_lpd / LPD_PER_COLLECTOR

    # Step C: Financials
    total_cost = (recommended_lpd / 100) * COST_PER_100_LPD
    daily_kwh_saved = (recommended_lpd / 100) * KWH_SAVED_PER_100L
    annual_savings = daily_kwh_saved * 365 * TARIFF

    if annual_savings > 0:
        payback_period = total_cost / annual_savings
    else:
        payback_period = 0

    print("\n--- Thermal System Results ---")
    print(f"Recommended System Size: {recommended_lpd:.0f} LPD")
    print(f"Thermal Collectors Required: {int(final_collectors_needed)} panels")
    print(f"Total Cost: {total_cost:,.2f}")
    print(f"Equivalent Electrical Savings: {annual_savings:,.2f} per year")
    print(f"Payback Period: {payback_period:.2f} years")

# --- PIPELINE 3: ERROR HANDLING ---
else:
    print("\nInvalid selection. Please run the script again and type exactly 1 or 2.")