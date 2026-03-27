import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.preprocessing import StandardScaler, MinMaxScaler
import plotly.graph_objects as go
import io
import plotly.express as px

st.set_page_config(page_title="Marketing Budget Optimizer", layout="wide")
st.title("💰 Marketing Budget Optimizer")
st.markdown(
                """ 
                <div style="height: 5px; background-color: black; margin: 10px 0;"></div>
                """, 
                unsafe_allow_html=True
            )

# Logistic and adstock functions
def logistic_function(x, growth_rate, midpoint):
    return 1 / (1 + np.exp(-growth_rate * (x - midpoint)))

def adstock_function(x, carryover_rate):
    x = np.array(x)
    result = np.zeros_like(x)
    result[0] = x[0]
    for i in range(1, len(x)):
        result[i] = x[i] + carryover_rate * result[i - 1]
    return result

def apply_transformations_with_contributions(df, region_weight_df):
    """
    Applies adstock, logistic transformations, and standardization to the original DataFrame,
    and calculates contributions of each variable by multiplying betas with scaled and transformed variables.

    Parameters:
    - df: The DataFrame containing the original data (media and other variables).
    - region_weight_df: DataFrame containing region weights and transformation parameters.

    Returns:
    - DataFrame: Transformed data with contribution columns.
    """
    transformed_data_list = []  # To store transformed data for each region
    unique_regions = region_weight_df["Region"].unique()
    brand = region_weight_df["Brand"].unique()

 
    # Extract media variables dynamically
    media_variables = [
        col.replace('_adjusted', '')
        for col in region_weight_df.columns
        if col.endswith('_adjusted') 
    ]
    # st.write(media_variables)

    # Extract other variables dynamically
    other_variables = [
        col.replace('beta_scaled_', '')
        for col in region_weight_df.columns
        if col.startswith('beta_scaled_')
    ]
    # print(other_variables)

    # Include beta0 in the calculations
    if 'beta0' in region_weight_df.columns:
        include_beta0 = True
    else:
        include_beta0 = False



    # Filter data by Region and Brand
    filtered_data = {
        region: df[(df["Region"] == region) & (df["Brand"].isin(brand))].copy()
        for region in unique_regions
    }
    
    for region in unique_regions:
        brand = region_weight_df.loc[region_weight_df["Region"] == region].iloc[0]
        region_df = filtered_data.get((region), pd.DataFrame())

        if region_df.empty:
            print(f"Warning: No data found for Region={region}, Brand={brand}. Skipping.")
            continue

        region_row = region_weight_df[region_weight_df["Region"] == region].iloc[0]

        # Add beta0 contribution if available
        if include_beta0:
            beta0_value = float(region_row['beta0'])
            region_df['beta0'] = beta0_value

        # Fetch transformation type
        transformation_type = region_row.get("Transformation_type", "logistic")

        # --- Handle transformation-specific parameters ---
        if transformation_type == "logistic":
            growth_rates = list(map(float, str(region_row.get("Growth_rate", "")).split(',')))
            carryovers = list(map(float, str(region_row.get("Carryover", "")).split(',')))
            mid_points = list(map(float, str(region_row.get("Mid_point", "")).split(',')))
            # st.write(region,growth_rates,carryovers,mid_points)
            

            # If uniform, broadcast
            if len(set(growth_rates)) == 1 and len(set(carryovers)) == 1 and len(set(mid_points)) == 1:
                growth_rates *= len(media_variables)
                carryovers *= len(media_variables)
                mid_points *= len(media_variables)

        elif transformation_type == "power":
            carryovers = list(map(float, str(region_row.get("Carryover", "")).split(',')))
            powers = list(map(float, str(region_row.get("Power", "")).split(',')))

            # If uniform, broadcast
            if len(set(carryovers)) == 1 and len(set(powers)) == 1:
                carryovers *= len(media_variables)
                powers *= len(media_variables)

        else:
            raise ValueError(f"Unsupported Transformation_type: {transformation_type}")

        standardization_method = region_row["Standardization_method"]

        # Choose standardization method
        if standardization_method == 'minmax':
            scaler_class = MinMaxScaler
            scaler_params = {'feature_range': (0, 1)}
        elif standardization_method == 'zscore':
            scaler_class = StandardScaler
            scaler_params = {}
        elif standardization_method == 'none':
            scaler_class = None  # No scaling
        else:
            raise ValueError(f"Unsupported standardization method: {standardization_method}")


        # Standardize other variables
        for var in other_variables:
            if var in region_df.columns:
                if scaler_class:
                    scaler = scaler_class(**scaler_params)
                    region_df[f"scaled_{var}"] = scaler.fit_transform(region_df[[var]])
                else:
                    region_df[f"scaled_{var}"] = region_df[var]

    
        # --- Transform media variables ---
        for idx_var, media_var in enumerate(media_variables):
            if media_var not in region_df.columns:
                continue

            # Apply carryover/adstock
            carryover = carryovers[idx_var]
            beta_col = f"{media_var}_adjusted"
            adstocked = adstock_function(region_df[media_var].values, carryover)
            region_df[f"{media_var}_Adstock"] = adstocked

            # Standardize adstocked media
            standardized = (adstocked - np.mean(adstocked)) / np.std(adstocked)
            region_df[f"{media_var}_Ad_Std"] = standardized

            if transformation_type == "logistic":
                growth_rate = growth_rates[idx_var]
                mid_point = mid_points[idx_var]
                transformed = logistic_function(standardized, growth_rate, mid_point)
            

            elif transformation_type == "power":
                power = powers[idx_var]
                transformed = np.power(np.maximum(standardized, 0), power)

            # Handle NaNs
            transformed = np.nan_to_num(transformed)
            region_df[f"{media_var}_Transformed_Base"] = transformed
            # st.write(carryover,growth_rate,mid_point)

            # Apply final standardization
            if scaler_class:
                scaler = scaler_class(**scaler_params)
                transformed = scaler.fit_transform(
                    region_df[[f"{media_var}_Transformed_Base"]]
                )
            #     # Calculate contribution if beta is available
            #     if beta_col in region_row:
            #         beta_value = float(region_row[beta_col])
            #         region_df[f"{media_var}_contribution"] = beta_value * transformed
            # else:
            region_df[f"{media_var}_transformed"] = transformed

            # Calculate contribution if beta is available
            if beta_col in region_row:
                beta_value = float(region_row[beta_col])
                region_df[f"{media_var}_contribution"] = beta_value * transformed
                

        # Calculate contributions for other variables
        for var in other_variables:
            beta_col = f"beta_scaled_{var}"
            if beta_col in region_row and f"scaled_{var}" in region_df.columns:
                beta_value = float(region_row[beta_col])
                region_df[f"{var}_contribution"] = beta_value * (region_df[f"scaled_{var}"])
                

        transformed_data_list.append(region_df)

    # Concatenate all transformed data
    transformed_df = pd.concat(transformed_data_list, axis=0).reset_index(drop=True)
    return transformed_df


# senior_planner_multi_market.py
# Streamlit app to optimize budget allocation across multiple markets for one brand
# Author: You + ChatGPT (multi-market extension)

import numpy as np
import pandas as pd
import streamlit as st
from scipy.optimize import minimize

# ======================================
# --------- APP CONFIG / HEADER --------
# ======================================
# st.set_page_config(page_title="Multi-Market Budget Optimizer", layout="wide")
st.title("📊 Multi-Market Budget Optimizer (TV + Digital)")
st.caption("Optimize a single brand budget across all markets to maximize predicted volume")

# ======================================
# --------- HELPER / UTILITIES ---------
# ======================================

def adstock_function(x, carryover_rate):
    """Geometric adstock."""
    x = np.array(x, dtype=float)
    if len(x) == 0:
        return x
    result = np.zeros_like(x)
    result[0] = x[0]
    for i in range(1, len(x)):
        result[i] = x[i] + carryover_rate * result[i - 1]
    return result

# NOTE: You must have this function defined elsewhere in your project.
# It should return a DataFrame that includes at least:
# - TV_Reach, Digital_Reach
# - TV_Reach_Adstock, Digital_Reach_Adstock
# - TV_Reach_transformed, Digital_Reach_transformed
# - TV_Reach_Transformed_Base, Digital_Reach_Transformed_Base
# def apply_transformations_with_contributions(df, market_weights_df):
#     raise NotImplementedError("Please include your existing implementation.")

# ======================================
# ---------- FILE UPLOADERS ------------
# ======================================
st.sidebar.header("Upload Inputs")

model_data = st.sidebar.file_uploader("Upload file used for Modeling (Base data)", type=["csv", "xlsx"])
market_weights_file = st.sidebar.file_uploader("Upload Final Model Results", type=["csv", "xlsx"])

if model_data is None or market_weights_file is None:
    st.info("⬅️ Please upload both files to proceed.")
    st.stop()

import pandas as pd

def load_max_reach_excel(filepath, sheet_name="updated constraint"):
    """
    Load max reach constraints from Excel.
    Expected columns: Region, Brand, Media, Max_Reach
    """
    df = pd.read_excel(filepath, sheet_name=sheet_name)

    # Normalize column names
    df.columns = [c.strip() for c in df.columns]

    # Ensure required columns exist
    required = {"Region", "Media_variables", "Max_reach", "Min_reach"}
    if not required.issubset(df.columns):
        raise ValueError(f"Excel must contain columns: {required}")

    # Drop rows with missing Max_reach
    df = df.dropna(subset=["Max_reach"])

    return df

uploaded_file = st.sidebar.file_uploader("📂 Upload Max Reach Excel", type=["xlsx"])

if uploaded_file:
    max_reach_df = load_max_reach_excel(uploaded_file)
    # st.write("✅ Max Reach Data Loaded:", max_reach_df.head())
else:
    max_reach_df = None
# st.write(max_reach_df)
# max_reach_df = max_reach_df[max_reach_df["Brand"] == selected_brand] if max_reach_df is not None else None
# st.write(max_reach_df)


# ======================================
# -------- READ MODELING DATA ----------
# ======================================
try:
    if model_data.name.endswith(".csv"):
        # CSVs don't support sheet_name, so just read
        df = pd.read_csv(model_data)
    else:
        # Default to first sheet unless you want to expose selection
        df = pd.read_excel(model_data, sheet_name="Sheet1")
except Exception as e:
    st.error(f"Error loading Modeling file: {e}")
    st.stop()

import pandas as pd

# Select spend columns
spend_cols = ["AllMedia_Spends"]

df_current_media_spend = df[(df["Region"]!="All India")& (df["Fiscal Year"] == "FY25")]

# Group by Brand and Market to get total spends
brand_market_spends = df_current_media_spend.groupby(["Brand", "Region"])[spend_cols].sum().reset_index()

# Group by Brand to get brand-level totals
brand_totals = brand_market_spends.groupby("Brand")[spend_cols].sum().reset_index()
brand_totals = brand_totals.rename(columns={col: f"{col}_BrandTotal" for col in spend_cols})

# Merge back to compute shares
brand_share_df = brand_market_spends.merge(brand_totals, on="Brand")

# Calculate share of each market's spend vs. brand total
for col in spend_cols:
    brand_share_df[f"{col}_Share"] = (brand_share_df[col] / brand_share_df[f"{col}_BrandTotal"]) * 100
    # Format in percentage string with 1 decimal place
    brand_share_df[f"{col}_Share"] = brand_share_df[f"{col}_Share"].map(lambda x: f"{x:.1f}%")

# Final output
brand_share_df = brand_share_df[["Brand", "Region"] + spend_cols + [f"{col}_Share" for col in spend_cols]]


# st.dataframe(brand_share_df)


# ======================================
# ----- READ MARKET WEIGHTS / BETAS ----
# ======================================
col_sheets, col_brand = st.columns([1,1])

try:
    if market_weights_file.name.endswith(".csv"):
        market_weights_df = pd.read_csv(market_weights_file)
        sheet_names = ["<csv>"]
        selected_sheet = sheet_names[0]
    else:
        excel_file = pd.ExcelFile(market_weights_file)
        sheet_names = excel_file.sheet_names
        with col_sheets:
            selected_sheet = st.selectbox("Select Brand Sheet (from Final Model Results)", sheet_names)
        market_weights_df = pd.read_excel(excel_file, sheet_name=selected_sheet)
except Exception as e:
    st.error(f"Error loading Final Model Results: {e}")
    st.stop()

# Standardize column names similar to your snippet (beta_*_transformed => *_adjusted)
market_weights_df.rename(
    columns={
        col: col.replace('beta_', '').replace('_transformed', '_adjusted')
        for col in market_weights_df.columns
        if col.endswith('_transformed') and col.startswith('beta_')
    },
    inplace=True
)

# ======================================
# --------- BRAND SELECTION ------------
# ======================================
if "Brand" not in market_weights_df.columns:
    st.error("`Brand` column not found in Final Model Results file.")
    st.stop()

# with col_brand:
#     selected_brand = st.selectbox("Select Brand", sorted(market_weights_df["Brand"].dropna().unique()))
#     st.write(f"Selected Brand: {selected_brand}")

selected_brand = market_weights_df["Brand"].unique()[0]
# st.write(f"Available Brands: {selected_brand}")
# brand_weights_df = market_weights_df[market_weights_df["Brand"] == selected_brand].copy()
brand_weights_df = market_weights_df.copy()
if brand_weights_df.empty:
    st.error("No rows found for the selected brand.")
    st.stop()

# ======================================
# ------ APPLY TRANSFORMATIONS ----------
# ======================================
# We only need columns used by transformations & final stats; start from df
if not set(["Region", "Brand", "Date"]).issubset(df.columns):
    st.error("Base data must have columns: Region, Brand, Date (and media fields).")
    st.stop()

# NOTE: For initial transform we only need base reach columns at least.
# If your transformation function needs additional fields, ensure df contains them.
try:
    # You likely need the raw TV_Reach, Digital_Reach in df; ensure present or computed upstream
    # df = df[["Region", "Brand", "Date","Fiscal Year", "TV_Reach", "Digital_Reach","TV_Spends", "Digital_Spends"]]
    transformed_df_full = apply_transformations_with_contributions(df, brand_weights_df)
    # st.dataframe(transformed_df_full[transformed_df_full["Region"] == "Delhi-NCR"])
except Exception as e:
    st.error(f"Error in apply_transformations_with_contributions: {e}")
    st.stop()

# ======================================
# --- PREP LATEST FY + CPR PER MARKET ---
# ======================================
# Compute CPR from the latest FY per market based on your earlier snippet
required_cols = {"Fiscal Year", "TV_Spends", "Digital_Spends", "TV_Reach", "Digital_Reach"}
missing_req = required_cols - set(transformed_df_full.columns)
if missing_req:
    st.error(f"Transformed data missing columns: {missing_req}")
    st.stop()

# Allow user to set budget increase %
st.subheader("🔧 Budget & Assumptions")
col_b1, col_b2, col_b3 = st.columns([1,1,1])
# with col_b1:
#     budget_increase_pct = st.slider("Budget Increase % from Last FY (Brand total)", min_value=0, max_value=200, value=5, step=1)
# with col_b1:
#     budget_increase_pct = st.number_input(
#         "Budget Increase % from Last FY (Brand total)",
#         min_value=0.0000,
#         max_value=100.0,
#         value=0.0,
#         step=0.001,
#         format="%.3f"
#     )
with col_b1:
    mode = st.radio(
        "Choose budget increase type:",
        ("Percentage (%)", "Absolute Amount"),
        horizontal=True
    )

    if mode == "Percentage (%)":
        budget_increase_pct = st.number_input(
            "Budget Increase % from Last FY (Brand total)",
            min_value=0.000,
            max_value=100.0,
            value=5.0,
            step=0.001,
            format="%.3f"
        )
        budget_increase_abs = None

    else:
        budget_increase_abs = st.number_input(
            "Absolute Increase in Budget (Brand total)",
            min_value=0.0,
            value=0.0,
            step=1000.0,
            format="%.0f"
        )
        budget_increase_pct = None



# ======================================
# ----- BUILD PER-MARKET INPUT DICT -----
# ======================================
markets = sorted(brand_weights_df["Region"].dropna().unique())
# st.write("Markets found for the selected brand:", markets[6:])
# markets = markets[6:]
with col_brand:
    select_market = st.multiselect("Select Market", markets, default=markets)
    if len(select_market) == 0:
        st.error("No markets found for the selected brand.")
        st.stop()

market_data = {}
baseline_total_spend_brand = 0.0

# Helper to safely parse carryover
def parse_carryover(row, media_vars):
    try:
        carryover_list = [float(c.strip()) for c in str(row.get("Carryover", "")).split(",")]
        carryover_digital = carryover_list[media_vars.index('Digital_Reach_adjusted')]
        carryover_tv = carryover_list[media_vars.index('TV_Reach_adjusted')]
        return carryover_tv, carryover_digital
    except Exception:
        # default small carryover if not provided
        return 0.3, 0.3

# Helper to safely parse carryover
def parse_midpoint(row, media_vars):
    try:
        midpoint_list = [float(c.strip()) for c in str(row.get("Mid_point", "")).split(",")]
        midpoint_digital = midpoint_list[media_vars.index('Digital_Reach_adjusted')]
        midpoint_tv = midpoint_list[media_vars.index('TV_Reach_adjusted')]
        return midpoint_tv, midpoint_digital
    except Exception:
        # default small carryover if not provided
        return 0, 0
with st.expander("⚙️ Market CPR Settings (from latest FY)"):
    for region in select_market:
        # weights row for this market + brand
        rows = brand_weights_df[(brand_weights_df["Region"] == region) & (brand_weights_df["Brand"] == selected_brand)]
        if rows.empty:
            continue
        mw_row = rows.iloc[0]

        # Market-specific slice of transformed data
        mdf = transformed_df_full[(transformed_df_full["Region"] == region) & (transformed_df_full["Brand"] == selected_brand)].copy()
        # st.dataframe(mdf)
        # st.write(mdf.columns)
        if mdf.empty:
            continue

        # Latest FY for this market
        fy_list = sorted(mdf["Fiscal Year"].dropna().unique())
        if not fy_list:
            continue
        latest_fy = fy_list[-1]
        recent_df = mdf[mdf["Fiscal Year"] == latest_fy].copy()
        # st.write(f"Region: {region}, Latest FY: {latest_fy}, Rows: {len(recent_df)}")
        recent_df = apply_transformations_with_contributions(recent_df, brand_weights_df)
        # st.dataframe(recent_df)

        # Spend / Reach aggregates
        total_tv_spend = float(recent_df["TV_Spends"].sum())
        total_digital_spend = float(recent_df["Digital_Spends"].sum())
        total_tv_reach = float(recent_df["TV_Reach"].sum())
        total_digital_reach = float(recent_df["Digital_Reach"].sum())
        if selected_brand == "Aer O":
            total_volume = float(recent_df["Sales_Qty_Total"].sum())
        else:
            total_volume = float(recent_df["Volume"].sum())

        # Avoid div-by-zero CPRs
        current_tv_cpr = (total_tv_spend / total_tv_reach) if total_tv_reach > 0 else 0.0
        current_digital_cpr = (total_digital_spend / total_digital_reach) if total_digital_reach > 0 else 0.0

        # Accumulate baseline brand spend
        baseline_total_spend_brand = (total_tv_spend + total_digital_spend)

        # Betas
        try:
            beta_tv = float(mw_row["TV_Reach_adjusted"])
        except Exception:
            beta_tv = 0.0
        try:
            beta_digital = float(mw_row["Digital_Reach_adjusted"])
        except Exception:
            beta_digital = 0.0

        # Base contribution (beta0 + non-media + other adjusted channels except TV/Digital)
        beta0 = float(mw_row["beta0"]) if "beta0" in mw_row else 0.0
        base_contribution = beta0

        # Add scaled non-media contributions if present
        for col in brand_weights_df.columns:
            if str(col).startswith("beta_scaled_"):
                var = str(col).replace("beta_scaled_", "")
                scaled_col = f"scaled_{var}"
                if scaled_col in mdf.columns:
                    base_contribution += float(mw_row[col]) * float(mdf[scaled_col].mean())

        # st.write(f"Region: {region}, Base Contribution (before media): {base_contribution}")

        # Add other adjusted channels contributions (mean transformed)
        for col in mw_row.index:
            if str(col).endswith("_adjusted") and col not in ["TV_Reach_adjusted", "Digital_Reach_adjusted"]:
                base_name = col.replace("_adjusted", "")
                transformed_col = f"{base_name}_transformed"
                if transformed_col in mdf.columns:
                    base_contribution += float(mw_row[col]) * float(mdf[transformed_col].mean())

        # st.write(f"Region: {region}, Base Contribution: {base_contribution}")

        # Reach lists
        r_tv_list = recent_df["TV_Reach"].tolist()
        r_dig_list = recent_df["Digital_Reach"].tolist()
        r_tv_spend = recent_df["TV_Spends"].tolist()
        r_dig_spend = recent_df["Digital_Spends"].tolist()

        # Carryover parse
        media_vars = [c for c in mw_row.index if str(c).endswith("_adjusted")]
        carryover_tv, carryover_digital = parse_carryover(mw_row, media_vars)
        mid_point_tv, mid_point_digital = parse_midpoint(mw_row, media_vars)

        # Means / std of adstock, and min / max of transformed base (logistic space)
        # (guard against missing columns)
        def safe_mean(series_name):
            return float(recent_df[series_name].mean()) if series_name in recent_df.columns else 0.0

        def safe_std(series_name):
            return float(recent_df[series_name].std(ddof=0)) if series_name in recent_df.columns else 1.0

        def safe_min(series_name):
            return float(recent_df[series_name].min()) if series_name in recent_df.columns else 0.0

        def safe_max(series_name):
            return float(recent_df[series_name].max()) if series_name in recent_df.columns else 1.0

        mu_x = float(recent_df["TV_Reach_Adstock"].mean())  #safe_mean("TV_Reach_Adstock")
        sigma_x = safe_std("TV_Reach_Adstock")
        mu_y = safe_mean("Digital_Reach_Adstock")
        sigma_y = safe_std("Digital_Reach_Adstock")

        min_x = safe_min("TV_Reach_Transformed_Base")
        max_x = safe_max("TV_Reach_Transformed_Base")
        min_y = safe_min("Digital_Reach_Transformed_Base")
        max_y = safe_max("Digital_Reach_Transformed_Base")
        # st.write(f"Region: {region}, TV Adstock mean: {mu_x}, std: {sigma_x}, min: {min_x}, max: {max_x}")
        # st.write(f"Region: {region}, Digital Adstock mean: {mu_y}, std: {sigma_y}, min: {min_y}, max: {max_y}")

        # Current transformed means for prev_vol calc
        current_tv_trans_mean = safe_mean("TV_Reach_transformed")
        current_dig_trans_mean = safe_mean("Digital_Reach_transformed")

        x_std = (mu_x - mu_x) / sigma_x if sigma_x != 0 else 0.0
        y_std = (mu_y - mu_y) / sigma_y if sigma_y != 0 else 0.0
        # st.write(f"Region: {region}, TV std: {x_std}, Digital std: {y_std}")

        x_log = 1.0 / (1.0 + np.exp(-(3.5 * (x_std-mid_point_tv))))
        y_log = 1.0 / (1.0 + np.exp(-(3.5 * (y_std-mid_point_digital))))
        # st.write(f"Logistic params: TV growth=3.5, mid={mid_point_tv}; Digital growth=3.5, mid={mid_point_digital}")
        # st.write(f"Region: {region}, TV log: {x_log}, Digital log: {y_log}")

        x_final = (x_log - min_x) / (max_x - min_x) if max_x != min_x else 0.0
        y_final = (y_log - min_y) / (max_y - min_y) if max_y != min_y else 0.0
        # st.write(f"Region: {region}, TV final: {x_final}, Digital final: {y_final}")

        # Previous volume baseline (as in your one-market code)
        prev_vol = base_contribution + beta_tv * x_final + beta_digital * y_final

        # st.write(f"Region: {region}, base_contribution: {base_contribution}, tv_contribution: {beta_tv * x_final}, beta_digital: {beta_digital * y_final}")

        constant = base_contribution
        tv_contribution = beta_tv * x_final + constant + beta_digital * current_dig_trans_mean
        digital_contribution = beta_digital * y_final + constant + beta_tv * current_tv_trans_mean

        # with st.expander(f"⚙️ {region} CPR Settings"):

            # CPR inputs displayed nicely
            # st.markdown(f"### {region}")  # Market name as header

        col1, col2 = st.columns(2)

        with col1:
            tv_cpr = st.number_input(
                f"TV CPR ({region})", 
                value=current_tv_cpr, 
                step=0.01, 
                format="%.2f"
            )
            st.metric(
                f"TV ROI ({region})", 
                round(mw_row["ROI_weighted_TV_Reach"], 2) if "ROI_weighted_TV_Reach" in mw_row else 0.0
            )
        with col2:
            digital_cpr = st.number_input(
                f"Digital CPR ({region})", 
                value=current_digital_cpr, 
                step=0.01, 
                format="%.2f"
            )
            st.metric(
                f"Digital ROI ({region})", 
                round(mw_row["ROI_weighted_Digital_Reach"], 2) if "ROI_weighted_Digital_Reach" in mw_row else 0.0
            )


        market_data[region] = {
            # "Brand": selected_brand,
            "Region": region,
            "beta_tv": beta_tv,
            "beta_digital": beta_digital,
            "C": base_contribution,
            "prev_vol": prev_vol,
            "Total FY25 Volume": total_volume,
            "current_tv_trans_mean": current_tv_trans_mean,
            "current_dig_trans_mean": current_dig_trans_mean,
            "mu_x": mu_x, "sigma_x": sigma_x, "min_x": min_x, "max_x": max_x,
            "mu_y": mu_y, "sigma_y": sigma_y, "min_y": min_y, "max_y": max_y,
            "r_tv_list": r_tv_list,
            "r_dig_list": r_dig_list,
            "r_tv_spend": r_tv_spend,
            "r_dig_spend": r_dig_spend,
            "carryover_tv": carryover_tv,
            "carryover_digital": carryover_digital,
            "mid_point_tv": mid_point_tv,
            "mid_point_digital": mid_point_digital,
            "tv_cpr": tv_cpr,
            "digital_cpr": digital_cpr,
            "TV contribution": tv_contribution,
            "Digital contribution": digital_contribution,
            # "tv_cpr": st.number_input(f"TV CPR for {region}", value=current_tv_cpr, step=0.01),
            # "digital_cpr": st.number_input(f"Digital CPR for {region}", value=current_digital_cpr, step=0.01),
            "current_spend": baseline_total_spend_brand
        }

# st.dataframe(market_data)
# st.write("Market Data Summary:")
# for region, data in market_data.items():
#     st.write(f"Region: {region}")
#     for key, value in data.items():
#         st.write(f"  {key}: {value}")
#     st.write("---")

# If no markets gathered, stop
if not market_data:
    st.error("No valid market data constructed for the selected brand.")
    st.stop()

# ======================================
# -------- TOTAL BRAND BUDGET ----------
# ======================================
regions_order = list(market_data.keys())  # fixed order for mapping decision variables
# regions_order = regions_order[-1:]
# st.write(f"Markets included in optimization: {regions_order}")
current_total_spend_brand = 0.0
total_prev_vol = 0.0
for region in regions_order:
    md = market_data[region]
    # st.write(f"Region: {region}, Current Spend: ₹ {md['current_spend']:,.0f}, TV CPR: ₹ {md['tv_cpr']:,.2f}, Digital CPR: ₹ {md['digital_cpr']:,.2f}")
    current_total_spend_brand += md["current_spend"]
    total_prev_vol += md["prev_vol"]

# st.write(f"Total Previous Volume: {total_prev_vol:,.0f}")
baseline_total_budget = current_total_spend_brand
# increased_total_budget = baseline_total_budget * (1 + budget_increase_pct / 100.0)
# st.write(increased_total_budget, baseline_total_budget)
# ✅ Safe calculation
if mode == "Percentage (%)" and budget_increase_pct is not None:
    increased_total_budget = baseline_total_budget * (1 + budget_increase_pct / 100.0)
elif mode == "Absolute Amount" and budget_increase_abs is not None:
    increased_total_budget = baseline_total_budget + budget_increase_abs
else:
    increased_total_budget = baseline_total_budget

extra_budget = increased_total_budget - baseline_total_budget

col_b2.metric("Baseline Brand Budget (Last FY)", f"₹ {baseline_total_budget:,.0f}")
col_b3.metric("Increased Brand Budget (Next FY)", f"₹ {increased_total_budget:,.0f}")

B = float(increased_total_budget)

# ======================================
# ----- OBJECTIVE & CONSTRAINTS --------
# ======================================



def objective(vars_vec, market_data, regions_order):
    """
    Maximize total volume improvement across multiple markets.
    vars_vec = [x_tv_r1, x_dig_r1, x_tv_r2, x_dig_r2, ..., x_tv_rk, x_dig_rk]
    """
    total_diff = 0.0

    for i, region in enumerate(regions_order):
        md = market_data[region]

        # unpack variables
        x = vars_vec[2*i]     # TV multiplier
        y = vars_vec[2*i + 1] # Digital multiplier
        # st.write(f"Region: {region}, TV Multiplier: {x}, Digital Multiplier: {y}")

        # new reach lists
        new_tv = [v * (1 + x) for v in md["r_tv_list"]]
        new_dig = [v * (1 + y) for v in md["r_dig_list"]]

        # adstock
        ad_tv = adstock_function(new_tv, md["carryover_tv"])
        ad_dig = adstock_function(new_dig, md["carryover_digital"])

        x_ad, y_ad = np.mean(ad_tv), np.mean(ad_dig)

        # standardize + logistic + rescale (TV)
        x_std = (x_ad - md["mu_x"]) / (md["sigma_x"]) if md["sigma_x"] != 0 else 1e-3
        x_log = 1 / (1 + np.exp(-3.5 * (x_std - md["mid_point_tv"])))
        x_final = (x_log - md["min_x"]) / (md["max_x"] - md["min_x"]) if md["max_x"] != md["min_x"] else 1e-6

        # standardize + logistic + rescale (Digital)
        y_std = (y_ad - md["mu_y"]) / (md["sigma_y"]) if md["sigma_y"] != 0 else 1e-3
        y_log = 1 / (1 + np.exp(-3.5 * (y_std - md["mid_point_digital"])))
        y_final = (y_log - md["min_y"]) / (md["max_y"] - md["min_y"]) if md["max_y"] != md["min_y"] else 1e-6

        print(f"Region: {region}, x_final: {x}, y_final: {y}")
    
        # volume prediction
        vol = md["beta_tv"] * x_final + md["beta_digital"] * y_final + md["C"]

        diff = vol #- md["prev_vol"]
        total_diff += diff
    print(f".......................................................................................................... {total_diff}")

    return -total_diff   # negative for maximization


def budget_constraint(vars_vec, market_data, regions_order, B):
    total_spend = 0.0
    for i, region in enumerate(regions_order):
        md = market_data[region]
        x = vars_vec[2*i]
        y = vars_vec[2*i + 1]

        total_spend += (
            md["tv_cpr"] * np.sum(md["r_tv_list"]) * (1 + x) +
            md["digital_cpr"] * np.sum(md["r_dig_list"]) * (1 + y)
        )
    return B - total_spend

#### Old constraint

# def market_budget_constraint(market_data, regions_order):
#     """Return list of constraints for TV and Digital separately per market."""
#     cons = []

#     with st.expander("⚙️ Per-Market Budget Constraints"):

#         for i, region in enumerate(regions_order):
#             md = market_data[region]

#             # Let user pick lower/upper multipliers for TV & Digital separately
#             st.subheader(f"📍 Constraints for {region}")
#             tv_lower_mult = st.number_input(
#                 f"TV Lower Bound Multiplier ({region})", value=0.0, step=0.1, key=f"tv_low_{region}"
#             )
#             tv_upper_mult = st.number_input(
#                 f"TV Upper Bound Multiplier ({region})", value=1.2, step=0.1, key=f"tv_up_{region}"
#             )
#             dig_lower_mult = st.number_input(
#                 f"Digital Lower Bound Multiplier ({region})", value=0.0, step=0.1, key=f"dig_low_{region}"
#             )
#             dig_upper_mult = st.number_input(
#                 f"Digital Upper Bound Multiplier ({region})", value=1.2, step=0.1, key=f"dig_up_{region}"
#             )

#             # Baseline spends
#             tv_current = np.sum(md["r_tv_list"]) * md["tv_cpr"]
#             dig_current = np.sum(md["r_dig_list"]) * md["digital_cpr"]

#             # --- TV constraints ---
#             cons.append({
#                 "type": "ineq",
#                 "fun": lambda v, i=i, tv_current=tv_current, tv_lower_mult=tv_lower_mult: (
#                     (tv_current * (1 + v[2*i])) - tv_current * tv_lower_mult
#                 )
#             })
#             cons.append({
#                 "type": "ineq",
#                 "fun": lambda v, i=i, tv_current=tv_current, tv_upper_mult=tv_upper_mult: (
#                     tv_current * tv_upper_mult - (tv_current * (1 + v[2*i]))
#                 )
#             })

#             # --- Digital constraints ---
#             cons.append({
#                 "type": "ineq",
#                 "fun": lambda v, i=i, dig_current=dig_current, dig_lower_mult=dig_lower_mult: (
#                     (dig_current * (1 + v[2*i+1])) - dig_current * dig_lower_mult
#                 )
#             })
#             cons.append({
#                 "type": "ineq",
#                 "fun": lambda v, i=i, dig_current=dig_current, dig_upper_mult=dig_upper_mult: (
#                     dig_current * dig_upper_mult - (dig_current * (1 + v[2*i+1]))
#                 )
#             })
            

#     return cons

#### new constraints

def market_budget_constraint(market_data, regions_order):
    """Return list of constraints for TV and Digital separately per market.
       Decision variable v = % change in reach, spend = reach × CPR.
    """
    cons = []

    with st.expander("⚙️ Per-Market Budget Constraints"):

        for i, region in enumerate(regions_order):
            md = market_data[region]

            # Let user pick lower/upper multipliers for TV & Digital separately
            st.subheader(f"📍 Constraints for {region}")
            tv_lower_mult = st.number_input(
                f"TV Lower Bound Multiplier ({region})", value=0.001, step=0.1, key=f"tv_low_{region}"
            )
            tv_upper_mult = st.number_input(
                f"TV Upper Bound Multiplier ({region})", value=3.0, step=0.1, key=f"tv_up_{region}"
            )
            dig_lower_mult = st.number_input(
                f"Digital Lower Bound Multiplier ({region})", value=0.001, step=0.1, key=f"dig_low_{region}"
            )
            dig_upper_mult = st.number_input(
                f"Digital Upper Bound Multiplier ({region})", value=4.0, step=0.1, key=f"dig_up_{region}"
            )

            # Baseline reach & spend
            tv_base_reach = np.mean(md["r_tv_list"])
            dig_base_reach = np.mean(md["r_dig_list"])
            tv_cpr = md["tv_cpr"]
            dig_cpr = md["digital_cpr"]

            tv_current = tv_base_reach * tv_cpr
            dig_current = dig_base_reach * dig_cpr

            # --- TV constraints ---
            cons.append({
                "type": "ineq",
                "fun": lambda v, i=i,
                           tv_base_reach=tv_base_reach, tv_cpr=tv_cpr,
                           tv_lower_mult=tv_lower_mult: (
                    (tv_base_reach * (1 + v[2*i]) * tv_cpr) - (tv_base_reach * tv_cpr * tv_lower_mult)
                )
            })
            cons.append({
                "type": "ineq",
                "fun": lambda v, i=i,
                           tv_base_reach=tv_base_reach, tv_cpr=tv_cpr,
                           tv_upper_mult=tv_upper_mult: (
                    (tv_base_reach * tv_cpr * tv_upper_mult) - (tv_base_reach * (1 + v[2*i]) * tv_cpr)
                )
            })

            # --- Digital constraints ---
            cons.append({
                "type": "ineq",
                "fun": lambda v, i=i,
                           dig_base_reach=dig_base_reach, dig_cpr=dig_cpr,
                           dig_lower_mult=dig_lower_mult: (
                    (dig_base_reach * (1 + v[2*i+1]) * dig_cpr) - (dig_base_reach * dig_cpr * dig_lower_mult)
                )
            })
            cons.append({
                "type": "ineq",
                "fun": lambda v, i=i,
                           dig_base_reach=dig_base_reach, dig_cpr=dig_cpr,
                           dig_upper_mult=dig_upper_mult: (
                    (dig_base_reach * dig_cpr * dig_upper_mult) - (dig_base_reach * (1 + v[2*i+1]) * dig_cpr)
                )
            })

    return cons

############ Max Reach Constraint ##################
#
#
#
###################################################

# import pandas as pd

# def load_max_reach_excel(filepath, sheet_name="updated constraint"):
#     """
#     Load max reach constraints from Excel.
#     Expected columns: Region, Brand, Media, Max_Reach
#     """
#     df = pd.read_excel(filepath, sheet_name=sheet_name)

#     # Normalize column names
#     df.columns = [c.strip() for c in df.columns]

#     # Ensure required columns exist
#     required = {"Region", "Media_variables", "Max_reach", "Min_reach"}
#     if not required.issubset(df.columns):
#         raise ValueError(f"Excel must contain columns: {required}")

#     # Drop rows with missing Max_reach
#     df = df.dropna(subset=["Max_reach"])

#     return df

# uploaded_file = st.sidebar.file_uploader("📂 Upload Max Reach Excel", type=["xlsx"])

# if uploaded_file:
#     max_reach_df = load_max_reach_excel(uploaded_file)
#     # st.write("✅ Max Reach Data Loaded:", max_reach_df.head())
# else:
#     max_reach_df = None
# # st.write(max_reach_df)
max_reach_df = max_reach_df[max_reach_df["Brand"] == selected_brand] if max_reach_df is not None else None
# # st.write(max_reach_df)


def max_reach_constraint(market_data, regions_order, max_reach_df=None, default_mult=1.2):
    """
    Build constraints to ensure that new reach <= max reach (or fallback).
    """
    cons = []

    for i, region in enumerate(regions_order):
        md = market_data[region]
        # brand = md["Brand"].iloc[0]

        tv_base_reach = np.mean(md["r_tv_list"])
        dig_base_reach = np.mean(md["r_dig_list"])
        tv_cpr = md["tv_cpr"]
        dig_cpr = md["digital_cpr"]

        # --- Find max reach from Excel (or fallback) ---
        def get_upper_bound(media, base_reach):
            if max_reach_df is not None:
                row = max_reach_df[
                    (max_reach_df["Region"] == region) &
                    # (max_reach_df["Brand"] == brand) &
                    (max_reach_df["Media_variables"] == media)
                ]
                if not row.empty:
                    max_reach = row["Max_reach"].iloc[0]
                    # st.write(f"Region: {region}, Media: {media}, Base Reach: {base_reach}, Max Reach from Excel: {max_reach}")
                    return max(base_reach, max_reach)  # at least base
                    # return max_reach
            return base_reach * default_mult  # fallback

        tv_upper_reach = get_upper_bound("TV_Reach", tv_base_reach)
        dig_upper_reach = get_upper_bound("Digital_Reach", dig_base_reach)
        # st.write(f"Region: {region}, TV Upper Reach: {tv_upper_reach}, Digital Upper Reach: {dig_upper_reach}")
        # st.write(f"Region: {region}, TV Max Reach: {tv_base_reach}, Digital Max Reach: {dig_base_reach}")


        # --- TV: ensure new reach <= upper bound ---
        cons.append({
            "type": "ineq",
            "fun": lambda v, i=i, tv_base_reach=tv_base_reach, tv_upper_reach=tv_upper_reach: (
                tv_upper_reach - (tv_base_reach * (1 + v[2*i])) + 1e-2
            )
        })

        # --- Digital: ensure new reach <= upper bound ---
        cons.append({
            "type": "ineq",
            "fun": lambda v, i=i, dig_base_reach=dig_base_reach, dig_upper_reach=dig_upper_reach: (
                dig_upper_reach - (dig_base_reach * (1 + v[2*i+1])) +1e-2
            )
        })

    return cons

def reach_constraints(
    market_data,
    regions_order,
    max_reach_df=None,
    default_max_mult=1.2,
    default_min_mult=0.8,
    months_in_year=12
):
    """
    Build constraints to ensure:
        yearly_min_reach <= total_yearly_reach <= yearly_max_reach

    Assumes Excel has yearly reach bounds, and r_tv_list / r_dig_list are monthly values.
    """

    cons = []

    for i, region in enumerate(regions_order):
        md = market_data[region]

        # --- use total yearly base reach ---
        tv_base_reach = np.sum(md["r_tv_list"])
        dig_base_reach = np.sum(md["r_dig_list"])

        # --- Excel-based or fallback bounds ---
        def get_bounds(media, base_reach):
            min_reach, max_reach = base_reach * default_min_mult, base_reach * default_max_mult
            if max_reach_df is not None:
                row = max_reach_df[
                    (max_reach_df["Region"] == region) &
                    (max_reach_df["Media_variables"] == media)
                ]
                if not row.empty:
                    if "Max_reach" in row.columns and not pd.isna(row["Max_reach"].iloc[0]):
                        max_reach_excel = row["Max_reach"].iloc[0]
                        # max_reach = max(base_reach, max_reach_excel)
                        max_reach = max_reach_excel
                        # if base_reach > max_reach:
                        #     max_reach = max_reach_excel  # allow lower than base if specified
                    if "Min_reach" in row.columns and not pd.isna(row["Min_reach"].iloc[0]):
                        min_reach_excel = row["Min_reach"].iloc[0]
                        min_reach = min(base_reach, min_reach_excel)
            return min_reach, max_reach

        tv_min, tv_max = get_bounds("TV_Reach", tv_base_reach)
        dig_min, dig_max = get_bounds("Digital_Reach", dig_base_reach)

        # --- TV constraints (yearly total) ---
        cons.append({
            "type": "ineq",
            "fun": lambda v, i=i, base=tv_base_reach, ub=tv_max: (
                ub - (base * (1 + v[2*i])) + 1e-2
            )
        })
        cons.append({
            "type": "ineq",
            "fun": lambda v, i=i, base=tv_base_reach, lb=tv_min: (
                (base * (1 + v[2*i])) - lb + 1e-2
            )
        })

        # --- Digital constraints (yearly total) ---
        cons.append({
            "type": "ineq",
            "fun": lambda v, i=i, base=dig_base_reach, ub=dig_max: (
                ub - (base * (1 + v[2*i+1])) + 1e-2
            )
        })
        cons.append({
            "type": "ineq",
            "fun": lambda v, i=i, base=dig_base_reach, lb=dig_min: (
                (base * (1 + v[2*i+1])) - lb + 1e-2
            )
        })

    return cons





# ======================================
# ------------- OPTIMIZE ---------------
# ======================================
# regions_order = list(market_data.keys())
n_vars = 2 * len(regions_order)
x0 = [0] * n_vars
bounds = [(-1, 1)] * n_vars

cons = [{
    'type': 'eq',
    'fun': lambda vars_vec: budget_constraint(vars_vec, market_data, regions_order, B)
}]

# Add per-market constraints
cons.extend(market_budget_constraint(market_data, regions_order))
# Add max reach constraints
# cons.extend(max_reach_constraint(market_data, regions_order, max_reach_df, default_mult=1.2))
# Add min/max reach constraints
cons.extend(reach_constraints(market_data, regions_order, max_reach_df, default_max_mult=3.0, default_min_mult=0.001))

############################################ old code ########################################

import plotly.graph_objects as go

# store history of (xk, vol)
history = []
history_volumes = []  # store only floats for plotting

# store best feasible solution
best_solution = {"vol": -1e18, "x": None}

def callbackF(xk):
    """Callback after each iteration"""
    val = objective(xk, market_data, regions_order)
    candidate_vol = -val  # convert back to positive volume

    # ---- check feasibility ----
    feasible = True
    for con in cons:
        if con["type"] == "eq":
            if abs(con["fun"](xk)) > 1e-6:
                feasible = False
                break
        elif con["type"] == "ineq":
            if con["fun"](xk) < -1e-6:
                feasible = False
                break

    # store history (with iterate)
    history.append({"x": xk.copy(), "vol": candidate_vol})
    history_volumes.append(candidate_vol)

    # if feasible, update best solution
    if feasible and candidate_vol > best_solution["vol"]:
        best_solution["vol"] = candidate_vol
        best_solution["x"] = xk.copy()



# 👇 log initial baseline BEFORE optimization runs
baseline_volume = sum(md["prev_vol"] for md in market_data.values())
init_val = objective(x0, market_data, regions_order)
history.append( -init_val)

###############################################################################

from scipy.optimize import minimize, NonlinearConstraint
import numpy as np

# --- global storage for feasible solutions ---
last_feasible = {"x": None, "fun": None}

def feasible_callback(xk, state):
    """
    Called at each iteration. Saves the last feasible solution.
    """
    global last_feasible

    # Check all constraints
    feas = all(c["fun"](xk) >= -1e-6 if c["type"] == "ineq" else abs(c["fun"](xk)) <= 1e-6 
               for c in cons)

    if feas:
        last_feasible["x"] = xk.copy()
        last_feasible["fun"] = objective(xk, market_data, regions_order)

st.subheader("🚀 Run Optimization")
with st.spinner("Optimizing across all markets..."):
    # res = minimize(
    #     objective, x0,
    #     args=(market_data, regions_order),
    #     bounds=bounds,
    #     constraints=cons,
    #     method='SLSQP',
    #     callback=callbackF,   # 👈 attach callback here
    #     options={'maxiter': 20000, 'ftol': 1e-1, 'disp': True}
    # )
    # res = minimize(
    #     objective,
    #     x0,
    #     args=(market_data, regions_order),
    #     method='trust-constr',
    #     bounds=bounds,
    #     constraints=cons,
    #     # callback=trust_constr_callback, # Add the new callback here
    #     options={
    #         'maxiter': 20000,
    #         'verbose': 3,
    #         'gtol': 1e-1,
    #         'xtol': 1e-3,
    #         'barrier_tol': 1e-1
    #     })
    res = minimize(
        objective,
        x0,
        args=(market_data, regions_order),
        method='trust-constr',
        bounds=bounds,
        constraints=cons,
        options={
            'maxiter': 5000,
            'verbose': 3,
            'gtol': 1e-1,
            'xtol': 1e-1,
            'barrier_tol': 1e-1,
            'finite_diff_rel_step': 1e-2,
            'factorization_method': 'SVDFactorization'
        }
    )

    # --- Post-check ---
    if res.success:
        final_solution = res.x
        # st.write("✅ Optimizer converged with solution:", final_solution)
    else:
        # st.write("⚠️ Optimizer failed, returning last feasible solution.")
        final_solution = last_feasible["x"]

    # st.write("🔹 Final feasible solution:", final_solution)



    optimized_diff = -res.fun
    optimized_volume =  optimized_diff

    # --- Plot with Plotly ---
    fig = go.Figure()

    # Optimization path
    fig.add_trace(go.Scatter(
        y=history,
        mode="lines+markers",
        name="Optimized Volume",
        line=dict(color="blue"),
        marker=dict(size=6)
    ))

    # Baseline volume line
    fig.add_hline(
        y=baseline_volume,
        line_dash="dash",
        line_color="red",
        annotation_text="Baseline Volume",
        annotation_position="top left"
    )

    # Final optimized point
    fig.add_trace(go.Scatter(
        x=[len(history)-1],
        y=[optimized_volume],
        mode="markers+text",
        text=["Final Volume"],
        textposition="top center",
        marker=dict(size=12, color="green", symbol="star"),
        name="Final Optimized"
    ))

    fig.update_layout(
        title="Optimization Progress",
        xaxis_title="Iteration",
        yaxis_title="Volume",
        template="plotly_white"
    )

    # st.plotly_chart(fig, use_container_width=True)

    # st.success("✅ Optimization complete!")
    # st.write(f"Baseline Volume: **{baseline_volume:,.0f}**")
    # st.write(f"Optimized Volume: **{optimized_volume:,.0f}**")
    # st.write(f"Gain: **{optimized_diff:,.0f}**")
    # st.write("Global Budget:", budget_constraint(res.x, market_data, regions_order, B))
    market_total = 0.0
    for i, region in enumerate(regions_order):
        tv_spend = (np.sum(market_data[region]["r_tv_list"]) * (1 + res.x[2*i])) * market_data[region]["tv_cpr"]
        dig_spend = (np.sum(market_data[region]["r_dig_list"]) * (1 + res.x[2*i+1])) * market_data[region]["digital_cpr"]
        total = tv_spend + dig_spend
        # st.write(region, "Spend:", total)
    
        market_total += total
    # Compute feasibility of global constraints
    # total_min = sum([market["current_spend"]*0.8 for market in market_data.values()])
    # total_max = sum([market["current_spend"]*1.2 for market in market_data.values()])

    # st.write("Global budget allowed range:", total_min, "to", total_max)
    # st.write("Target global budget:", B)
    base_total = sum(md["current_spend"] for md in market_data.values())
    # st.write("Baseline Spend:", base_total)
    # # st.write("Target Budget B:", B)
    # st.write("Target global budget:", B)

    # if not (total_min <= B <= total_max):
    #     st.write("❌ Infeasible problem: global budget is outside per-market limits")

# ### Printing History

# history = []

# def callbackF(xk):
#     fval = objective(xk, market_data, regions_order)
#     history.append((xk.copy(), fval))
#     st.write("Iteration:", len(history), "x:", xk, "objective:", -fval)  # negate because we minimized

# for i, (x, f) in enumerate(history):
#     st.write(f"Iter {i+1}: x = {x}, Objective = {-f}")

# ======================================
# -------- REPORT THE RESULTS ----------
# ======================================

# baseline_volume = sum(md["prev_vol"] for md in market_data.values())
# optimized_diff = -res.fun
# optimized_volume = optimized_diff

# if res.success or optimized_volume > baseline_volume:
#     st.success("✅ Optimization usable!")
#     st.write(f"Baseline Volume: {baseline_volume:,.0f}")
#     st.write(f"Optimized Volume: {optimized_volume:,.0f}")
#     st.write(f"Gain: {optimized_diff:,.0f}")
# else:
#     st.error("❌ Optimization failed.")
#     st.write(f"Reason: {res.message}")
#     st.info("Try adjusting bounds, reviewing CPRs, or checking transformed columns.")


# ======================================
# -------- REPORT THE RESULTS ----------
# ======================================

# if not res.success:
#     st.warning("⚠️ Optimization did not converge cleanly.")
#     st.write(f"Reason: {res.message}")

#     if best_solution["x"] is not None:
#         st.info("Using the best feasible solution found during iterations 👇")
#         solution_x = best_solution["x"]
#         optimized_volume = best_solution["vol"]
#     else:
#         st.error("❌ No feasible solution could be extracted.")
#         st.stop()
# else:
#     st.success("✅ Optimization successful!")
#     solution_x = res.x
#     optimized_volume = -res.fun

# # --- Summary ---
# st.subheader("📊 Optimization Summary")
# st.write(f"Baseline Volume: **{baseline_volume:,.0f}**")
# st.write(f"Optimized Volume: **{optimized_volume:,.0f}**")
# st.write(f"Gain: **{optimized_volume - baseline_volume:,.0f}**")
# st.write(f"Solution: **{solution_x}**")

# ======================================
# -------- REPORT THE RESULTS ----------
# ======================================

def is_feasible(x, cons, tol=1e-6):
    """Check if x satisfies all constraints within tolerance."""
    for con in cons:
        val = con["fun"](x)
        if isinstance(val, np.ndarray):
            if np.any(val < -tol):
                return False
        else:
            if val < -tol:
                return False
    return True

if history:
    # Normalize history so we can always access "vol" and "x"
    normalized = []
    for h in history:
        if isinstance(h, dict):
            normalized.append(h)
        else:  # float case, no x vector
            normalized.append({"x": None, "vol": h})

    best_entry = max(normalized, key=lambda h: h["vol"])
    best_volume_seen = best_entry["vol"]

    # Always keep best_solution as a dict {x, vol}
    best_solution = {"x": best_entry["x"], "vol": best_entry["vol"]}
else:
    best_entry = None
    best_volume_seen = None
    best_solution = {"x": None, "vol": None}



# best_entry = max(history, key=lambda h: h["vol"])
# best_solution = best_entry["x"]
# best_volume_seen = best_entry["vol"]

# st.write(f"Best volume seen during iterations: {best_volume_seen:,.0f}")
# st.write(f"Best solution x: {best_solution}")
# Pick best solution
# best_volume_seen = max(history) if history else None
# best_solution = None

# if res.success and is_feasible(res.x, cons):
#     best_solution = {"x": res.x, "vol": -objective(res.x, market_data, regions_order)}
#     st.success("✅ Optimization successful!")
# else:
#     st.warning("⚠️ Optimization did not converge cleanly.")
#     st.write(f"Reason: {res.message}")

#     if best_solution and best_solution["x"] is not None:
#         st.info("Using best feasible solution from history 👇")
#     else:
#         st.error("❌ No feasible solution could be extracted.")
#         st.stop()

# if best_solution and best_solution["x"] is not None:
#     st.success("📊 Final Feasible Solution Found")
#     st.write(f"Baseline Volume: **{baseline_volume:,.0f}**")
#     st.write(f"Optimized Volume: **{best_solution['vol']:,.0f}**")
#     st.write(f"Gain: **{best_solution['vol'] - baseline_volume:,.0f}**")






# # ======================================
# # -------- REPORT THE RESULTS ----------
# # ======================================

# best_volume_seen = max(history) if history else None

# if not res.success:
#     st.warning("⚠️ Optimization did not converge cleanly.")
#     st.write(f"Reason: {res.message}")

#     # If solver gave us a solution, use it
#     if res.x is not None and best_volume_seen is not None:
#         st.info("Using the best feasible solution found during iterations 👇")
#     else:
#         st.error("❌ No feasible solution could be extracted.")
#         st.stop()
# else:
#     st.success("✅ Optimization successful!")


# Build per-market summary
rows_out = []
idx = 0
total_new_spend = 0.0
total_prev_vol = 0.0
total_new_vol = 0.0
total_old_spend = 0.0
total_new_reach = 0.0

# for region in regions_order:
#     md = market_data[region]
#     x_opt = float(res.x[idx])
#     y_opt = float(res.x[idx + 1])
#     # x_opt = float(best_solution[idx])
#     # y_opt = float(best_solution[idx + 1])
#     idx += 2
# # if best_solution and len(best_solution) > 0:
# idx = 0
for i, region in enumerate(regions_order):
    md = market_data[region]
    x_opt = float(res.x[2*i])
    y_opt = float(res.x[2*i + 1])
    # region = md["Region"].iloc[0]
    region = md["Region"]
    # st.write(md)

    # st.write(f"{region}: TV {x_opt:.2%}, Digital {y_opt:.2%}")
    # idx += 2
    # st.write(f"### 📍 Results for {region}")
    # st.write(md)
    if max_reach_df is not None:
        row_tv = max_reach_df[
                        (max_reach_df["Region"] == region) &
                        # (max_reach_df["Brand"] == brand) &
                        (max_reach_df["Media_variables"] == "TV_Reach")
                    ]

        tv_max_reach = row_tv["Max_reach"].iloc[0] if not row_tv.empty else None
        tv_min_reach = row_tv["Min_reach"].iloc[0] if not row_tv.empty else None
        tv_max_spend = row_tv["Max_reach"].iloc[0] * md["tv_cpr"] if not row_tv.empty else None
        tv_min_spend = row_tv["Min_reach"].iloc[0] * md["tv_cpr"] if not row_tv.empty else None

        row_dig = max_reach_df[
                        (max_reach_df["Region"] == region) &
                        # (max_reach_df["Brand"] == brand) &
                        (max_reach_df["Media_variables"] == "Digital_Reach")
                    ]
        dig_max_reach = row_dig["Max_reach"].iloc[0] if not row_dig.empty else None
        dig_min_reach = row_dig["Min_reach"].iloc[0] if not row_dig.empty else None
        dig_max_spend = row_dig["Max_reach"].iloc[0] * md["digital_cpr"] if not row_dig.empty else None
        dig_min_spend = row_dig["Min_reach"].iloc[0] * md["digital_cpr"] if not row_dig.empty else None

    # New reach lists
    new_tv_list = [v * (1 + x_opt) for v in md["r_tv_list"]]
    new_dig_list = [v * (1 + y_opt) for v in md["r_dig_list"]]

    # New spend
    new_tv_spend = (np.sum(new_tv_list) * md["tv_cpr"]) if md["tv_cpr"] > 0 else 0.0
    new_dig_spend = (np.sum(new_dig_list) * md["digital_cpr"]) if md["digital_cpr"] > 0 else 0.0
    new_spend = new_tv_spend + new_dig_spend
    total_new_spend += new_spend
    # st.write(f"Region: {region}, TV Spend: {new_tv_spend}, Digital Spend: {new_dig_spend}")
    # lower = 0.2 * md["current_spend"]
    # upper = 2.0 * md["current_spend"]

    # st.write(f"{region}: Spend={new_spend:,.0f}, Allowed=[{lower:,.0f}, {upper:,.0f}]")
    # Current baseline spends
    current_tv_spend = np.sum(md["r_tv_spend"])
    current_dig_spend = np.sum(md["r_dig_spend"])

    # User-defined multipliers (already set in market_budget_constraint)
    tv_lower = current_tv_spend * st.session_state.get(f"tv_low_{region}", 0.8)
    tv_upper = current_tv_spend * st.session_state.get(f"tv_up_{region}", 1.2)
    dig_lower = current_dig_spend * st.session_state.get(f"dig_low_{region}", 0.8)
    dig_upper = current_dig_spend * st.session_state.get(f"dig_up_{region}", 1.2)

    # # Show allowed ranges
    # st.write(f"**{region}** — "
    #          f"TV Spend={new_tv_spend:,.0f} (Allowed [{tv_lower:,.0f}, {tv_upper:,.0f}]), "
    #          f"Digital Spend={new_dig_spend:,.0f} (Allowed [{dig_lower:,.0f}, {dig_upper:,.0f}])")


    # Recompute final volume for reporting using objective's logic
    ad_tv = adstock_function(new_tv_list, md["carryover_tv"])
    ad_dig = adstock_function(new_dig_list, md["carryover_digital"])

    x_ad = np.mean(ad_tv) if len(ad_tv) else 0.0
    y_ad = np.mean(ad_dig) if len(ad_dig) else 0.0
    # st.write(f"Region: {region}, TV Adstock Mean: {x_ad}, Digital Adstock Mean: {y_ad}")

    x_std = (x_ad - md["mu_x"]) / md["sigma_x"] if md["sigma_x"] != 0 else 0.0
    y_std = (y_ad - md["mu_y"]) / md["sigma_y"] if md["sigma_y"] != 0 else 0.0

    x_log = 1.0 / (1.0 + np.exp((-3.5 * (x_std-md["mid_point_tv"]))))
    y_log = 1.0 / (1.0 + np.exp((-3.5 * (y_std-md["mid_point_digital"]))))

    x_final = (x_log - md["min_x"]) / (md["max_x"] - md["min_x"]) if md["max_x"] != md["min_x"] else 0.0
    y_final = (y_log - md["min_y"]) / (md["max_y"] - md["min_y"]) if md["max_y"] != md["min_y"] else 0.0

    volume_final = md["beta_tv"] * x_final + md["beta_digital"] * y_final + md["C"]
    # st.write(f"Region: {region}, tv_contribution: {md["beta_tv"] * x_final}, digital_contribution: {md["beta_digital"] * y_final}")

    new_tv_contribution = md["beta_tv"] * x_final + md["C"]
    new_digital_contribution = md["beta_digital"] * y_final + md["C"]

    volume_prev = md["prev_vol"]
    uplift = volume_final - volume_prev
    uplift_pct = (uplift / volume_prev * 100.0) if volume_prev != 0 else 0.0

    old_spend = md["current_spend"]

    total_prev_vol += volume_prev
    total_new_vol += volume_final
    total_old_spend += md["current_spend"]
    total_new_reach += np.sum(new_tv_list) + np.sum(new_dig_list)

    

    rows_out.append({
        "Region": region,
        "TV %Δ Reach": f"{x_opt:.2%}",
        "Digital %Δ Reach": f"{y_opt:.2%}",
        "New Budget Share": new_spend / B if B > 0 else 0.0,
        # "Old Budget Share": old_spend / total_old_spend if total_old_spend > 0 else 0.0,
        "Extra budget share": (new_spend - md["current_spend"]) / extra_budget if extra_budget > 0 else 0.0,
        "New annual TV Reach": np.sum(new_tv_list),
        "New annual Digital Reach": np.sum(new_dig_list),
        # "New annual Reach": np.sum(new_tv_list) + np.sum(new_dig_list),
        # "New annual Share": (np.sum(new_tv_list) + np.sum(new_dig_list)) / total_new_reach if total_new_reach > 0 else 0.0,
        "New TV Share": np.sum(new_tv_list) / (np.sum(new_tv_list) + np.sum(new_dig_list)) if (np.sum(new_tv_list) + np.sum(new_dig_list)) > 0 else 0.0,
        "New Digital Share": np.sum(new_dig_list) / (np.sum(new_tv_list) + np.sum(new_dig_list)) if (np.sum(new_tv_list) + np.sum(new_dig_list)) > 0 else 0.0,
        "FY25 TV Reach": np.sum(md["r_tv_list"]),
        "FY25 Digital Reach": np.sum(md["r_dig_list"]),
        "FY25 TV Share": np.sum(md["r_tv_list"]) / (np.sum(md["r_tv_list"]) + np.sum(md["r_dig_list"])) if (np.sum(md["r_tv_list"]) + np.sum(md["r_dig_list"])) > 0 else 0.0,
        "FY25 Digital Share": np.sum(md["r_dig_list"]) / (np.sum(md["r_tv_list"]) + np.sum(md["r_dig_list"])) if (np.sum(md["r_tv_list"]) + np.sum(md["r_dig_list"])) > 0 else 0.0,
        "Max annual TV Reach": tv_max_reach,
        "Min annual TV Reach": tv_min_reach,
        "Max annual Digital Reach": dig_max_reach,
        "Min annual Digital Reach": dig_min_reach,
        "Max TV Spend": tv_max_spend,
        "Min TV Spend": tv_min_spend,
        "Max Digital Spend": dig_max_spend,
        "Min Digital Spend": dig_min_spend,
        "TV CPR": md["tv_cpr"],
        "Digital CPR": md["digital_cpr"],
        "New Total TV Spend": new_tv_spend,
        "New Total Digital Spend": new_dig_spend,
        "Constant": md["C"],
        # "New TV Contribution": new_tv_contribution,
        # "New Digital Contribution": new_digital_contribution,
        # "Old TV Contribution": md["TV contribution"],
        # "Old Digital Contribution": md["Digital contribution"],
        # "% Change in TV Contribution": (new_tv_contribution - md["TV contribution"]) / md["TV contribution"] * 100.0 if md["TV contribution"] != 0 else 0.0,
        # "% Change in Digital Contribution": (new_digital_contribution - md["Digital contribution"]) / md["Digital contribution"] * 100.0 if md["Digital contribution"] != 0 else 0.0,
        "Old Total Spend": md["current_spend"],
        "New Total Spend": new_spend,
        # "Extra budget share": (new_spend - md["current_spend"]) / extra_budget if extra_budget > 0 else 0.0,
        "% Change in Total Spend": (new_spend - md["current_spend"]) / md["current_spend"] * 100.0 if md["current_spend"] != 0 else 0.0,
        # "Budget Share": new_spend / B if B > 0 else 0.0,
        "Total FY25 Volume": md["Total FY25 Volume"],
        "Prev Volume": volume_prev,
        "New Volume": volume_final,
        "Uplift (Abs)": uplift,
        "Uplift (%)": uplift_pct / 100.0  # keep as ratio for formatting later
    })

results_df = pd.DataFrame(rows_out)
if not results_df.empty:
    results_df["New Budget Share"] = results_df["New Budget Share"].map(lambda v: f"{v:.2%}")
    # results_df["Old Budget Share"] = results_df["Old Budget Share"].map(lambda v: f"{v:.2%}")
    results_df["Extra budget share"] = results_df["Extra budget share"].map(lambda v: f"{v:.1%}")
    results_df["Uplift (%)"] = results_df["Uplift (%)"].map(lambda v: f"{v:.2%}")
    st.subheader("📋 Per-Market Optimal Allocation & Impact")
    results_df = results_df.fillna(0)
    st.dataframe(
        results_df.sort_values(by="New Total Spend", ascending=False)
                  .style.format({"New TV Spend":"₹ {:,.0f}",
                                 "New Digital Spend":"₹ {:,.0f}",
                                 "Old Total Spend":"₹ {:,.0f}",
                                 "Total FY25 Volume":"{:,.0f}",
                                 "New Total Spend":"₹ {:,.0f}",
                                 "New annual TV Reach":"{:,.0f}",
                                 "New annual Digital Reach":"{:,.0f}",
                                 "FY25 TV Reach":"{:,.0f}",
                                 "FY25 Digital Reach":"{:,.0f}",
                                 "Max annual TV Reach":"{:,.0f}",
                                 "Min annual TV Reach":"{:,.0f}",
                                 "Max annual Digital Reach":"{:,.0f}",
                                 "Min annual Digital Reach":"{:,.0f}",
                                 "Max TV Spend":"₹ {:,.0f}",
                                 "Min TV Spend":"₹ {:,.0f}",
                                 "Max Digital Spend":"₹ {:,.0f}",
                                 "Min Digital Spend":"₹ {:,.0f}",
                                 "TV CPR":"{:,.2f}",
                                 "Digital CPR":"{:,.2f}",
                                 "New Total TV Spend":"₹ {:,.0f}",
                                 "New Total Digital Spend":"₹ {:,.0f}",
                                 "% Change in Total Spend":"{:,.2f}%",
                                #  "% Change in TV Contribution":"{:,.2f}%",
                                #  "% Change in Digital Contribution":"{:,.2f}%",
                                 "Prev Volume":"{:,.2f}",
                                 "New Volume":"{:,.2f}",
                                 "Uplift (Abs)":"{:,.2f}"})
    )

# Constraint check
constraint_val = budget_constraint(res.x, market_data, regions_order, B)
col_t1, col_t2, col_t3, col_t4 = st.columns(4)
col_t1.metric("Total New Spend", f"₹ {total_new_spend:,.0f}")
col_t2.metric("Budget Constraint (should be ~0)", f"{constraint_val:,.6f}")
col_t3.metric("Total Volume Uplift", f"{(total_new_vol - total_prev_vol):,.2f}")
col_t4.metric("Total Volume Uplift %", f"{((total_new_vol - total_prev_vol) / total_prev_vol * 100.0 if total_prev_vol != 0 else 0):.2f}%")

st.markdown("---")
st.caption("Tip: If optimization fails or looks odd, check CPRs, carryover values, and transformed column availability.")
