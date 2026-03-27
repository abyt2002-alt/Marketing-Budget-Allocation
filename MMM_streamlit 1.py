import streamlit as st
import pandas as pd
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import warnings
warnings.filterwarnings('ignore')
from pykalman import KalmanFilter
import calendar
from streamlit_option_menu import option_menu
import os

# # Restrict access
# if "authenticated" not in st.session_state or not st.session_state.authenticated:
#     st.error("Unauthorized access! Please log in from the main page.")
#     st.stop()  # 🚫 Stop further execution if user is not logged in
st.set_page_config(page_title="MMM", layout="wide")

selected=option_menu(
        menu_title="",
        options=["PRE-PROCESS","EXPLORE","MODEL","EVALUATE","POST-MODEL ANALYSIS"],
        icons = ["sliders",         # PRE-PROCESS – tuning, adjustments
            "search",          # EXPLORE – data exploration
            "tools",           # ENGINEER – feature engineering
            "diagram-3",             # MODEL – training a model
            "bar-chart"]   ,    
        # icons=["database","diagram-3","clipboard-data"],
        orientation="horizontal"
    )

# st.title("D1 Preparation")
# st.subheader("Traial 2")

# tab1,tab2,tab3 = st.tabs(["D0 Basic Summary","Valiadate D0","D1 Preparation"])

# with tab1:

# Apply full-width tabs
st.markdown(
        """
        <style>
            div.stTabs button {
                flex-grow: 1;
                text-align: center;
            }
        </style>
        """,
        unsafe_allow_html=True
    )

if selected=="PRE-PROCESS":

    tab1,tab2,tab3 = st.tabs(["D0 Basic Summary","Valiadate D0","D1 Preparation"])

    with tab1:

        # st.write("## 📊 D0 Basic Summary")

        st.sidebar.write("Upload your D0 files for processing.")

        # File uploaders for Media D0 and Sales D0
        media_file = st.sidebar.file_uploader("Upload Media D0 File", type=["csv", "xlsx"], key="media")
        sales_file = st.sidebar.file_uploader("Upload Sales D0 File", type=["csv", "xlsx"], key="sales")

        def load_file(uploaded_file):
            """Helper function to read CSV or Excel files"""
            if uploaded_file is not None:
                if uploaded_file.name.endswith('.csv'):
                    return pd.read_csv(uploaded_file,sheet_name="Data")
                else:
                    return pd.read_excel(uploaded_file)
            return None
        
        # # Store uploaded files in session state
        # if media_file is not None:
        #     st.session_state["media_file_uploaded"] = media_file
        #     # st.session_state["media_d0"] = load_file(media_file)
        #     # st.sidebar.write("✅ Media D0 file uploaded successfully!")

        # if sales_file is not None:
        #     st.session_state["sales_file_uploaded"] = sales_file
        #     # st.session_state["sales_d0"] = load_file(sales_file)
        #     # st.sidebar.write("✅ Sales D0 file uploaded successfully!")

        # Handle and store uploads in session state
        if media_file is not None:
            st.session_state['media_file'] = media_file
            st.session_state['media_df'] = load_file(media_file)

        if sales_file is not None:
            st.session_state['sales_file'] = sales_file
            st.session_state['sales_df'] = load_file(sales_file)


        # Function to generate basic summary of the dataset
        def generate_summary(df, df_name):
            """Generate basic summary of dataset"""
            st.write(f"#### {df_name} - Dataset Summary:")

            # Show DataFrame Shape
            st.write(f"##### **Shape of Dataset:** `{df.shape[0]}` rows × `{df.shape[1]}` columns")

            # Create columns for better layout
            col1, col2, col3 = st.columns(3)

            # Column Names & Data Types
            with col1:
                st.write("###### Column Names & Data Types:")
                col_info = pd.DataFrame({"Column Name": df.columns, "Data Type": df.dtypes})
                st.dataframe(col_info, hide_index=True)

            # Null Values Count
            with col2:
                st.write("###### Null Values in Each Column:")
                null_counts = pd.DataFrame({"Column Name": df.columns, "Missing Values": df.isnull().sum()})
                st.dataframe(null_counts, hide_index=True)

            # Unique Values in Categorical Columns
            with col3:
                st.write("###### Unique Values in Categorical Columns:")
                cat_cols = df.select_dtypes(include=["object"]).columns
                if len(cat_cols) > 0:
                    unique_values_df = pd.DataFrame({"Column Name": cat_cols, "Unique Values": [df[col].nunique() for col in cat_cols]})
                    st.dataframe(unique_values_df, hide_index=True)
                    # Use an expander to show unique values on demand
                    with st.expander(f"View Unique Values in {df_name}"):
                        selected_col = st.selectbox(f"Select a categorical column in {df_name}:", cat_cols, key=f"select_{df_name}")
                        if selected_col:
                            st.write(f"**Unique values in {selected_col}:**")
                            # Show unique values in a table format
                            unique_df = pd.DataFrame({f"Unique Values in {selected_col}": df[selected_col].unique()})
                            st.dataframe(unique_df, hide_index=True)

                else:
                    st.write("No categorical columns found.")
        
        col5,col6 = st.columns(2)
        # with col5:

        #     # Load and display Media D0
        #     # if media_file:
        #     # Load and store in session state
        #     if 'media_df' not in st.session_state:
        #         # st.session_state['media_df'] = load_file(media_file)
            
        #         media_df = st.session_state['media_df']
                
        #         st.write("### Media D0 Preview:")
        #         st.dataframe(media_df.head())
        #         with st.expander("View whole dataset", expanded=False):
        #             st.dataframe(media_df)
        #         st.markdown(
        #         """ 
        #         <div style="height: 1px; background-color: black; margin: 15px 0;"></div>
        #         """, 
        #         unsafe_allow_html=True
        #         )  
                        
        #         # Button to view Media D0 Summary
        #         if st.checkbox("Show Media D0 Summary"):
        #             generate_summary(media_df, "Media D0")

        # with col6:
        #     # Load and display Sales D0
        #     # if sales_file:
        #         # st.success(f"Sales D0 file '{sales_file.name}' uploaded successfully!")
        #     if 'sales_df' not in st.session_state:
        #         # st.session_state['sales_df'] = load_file(sales_file)

        #         # Load and store in session state
        #         sales_df = st.session_state['sales_df']
        #         # sales_df = load_file(sales_file)
                
                
        #         st.write("### Sales D0 Preview:")
        #         st.dataframe(sales_df.head())
        #         with st.expander("View whole dataset", expanded=False):
        #             st.dataframe(sales_df)
        #         st.markdown(
        #         """ 
        #         <div style="height: 1px; background-color: black; margin: 15px 0;"></div>
        #         """, 
        #         unsafe_allow_html=True
        #         )

        #         # Button to view Sales D0 Summary
        #         if st.checkbox("Show Sales D0 Summary"):
        #             generate_summary(sales_df, "Sales D0")
        # Initialize as None
        media_df = None
        sales_df = None

        with col5:
            # Load and display Media D0
            if 'media_df' in st.session_state:
                media_df = st.session_state['media_df']

                st.write("### Media D0 Preview:")
                st.dataframe(media_df.head())
                with st.expander("View whole dataset", expanded=False):
                    st.dataframe(media_df)

                st.markdown(
                    """ 
                    <div style="height: 1px; background-color: black; margin: 15px 0;"></div>
                    """, 
                    unsafe_allow_html=True
                )  

                if st.checkbox("Show Media D0 Summary"):
                    generate_summary(media_df, "Media D0")

        with col6:
            # Load and display Sales D0
            if 'sales_df' in st.session_state:
                sales_df = st.session_state['sales_df']

                st.write("### Sales D0 Preview:")
                st.dataframe(sales_df.head())
                with st.expander("View whole dataset", expanded=False):
                    st.dataframe(sales_df)

                st.markdown(
                    """ 
                    <div style="height: 1px; background-color: black; margin: 15px 0;"></div>
                    """, 
                    unsafe_allow_html=True
                )  

                if st.checkbox("Show Sales D0 Summary"):
                    generate_summary(sales_df, "Sales D0")

    st.markdown(
                    """ 
                    <div style="height: 2px; background-color: black; margin: 15px 0;"></div>
                    """, 
                    unsafe_allow_html=True
                )  




    ##############################################################################################################################################################################################################
    ############################################################################################################################################################################################################
    ############################################################################################################################################################################################################
    ############################################################################################################################################################################################################
    # Define validation rules for Media D0 and Sales D0

    # Define validation rules for Media D0
    REQUIRED_COLUMNS_MEDIA = ["Market", "Channel", "Region","Category","SubCategory","Brand","Variant","PackType","PPG","PackSize","Year","Month","Week","Media Category", "Media Subcategory"]  # Example required columns for Media D0
    COLUMN_DTYPES_MEDIA = {"Amount_Spent": "float64","Year":"object"} #"Unique_Reach": "float64"
    NON_NULL_COLUMNS_MEDIA = ["Market", "Region","Category","SubCategory","Brand","Year","Month","Media Category", "Media Subcategory"]  # Columns that must not have null values in Media D0

    # Define validation rules for Sales D0
    REQUIRED_COLUMNS_SALES = ["Market", "Channel", "Region","Category","SubCategory","Brand","Variant","PackType","PPG","PackSize","Year","Month","Week","D1","Price"]  # Example required columns for Sales D0  ,"Volume","Sales"
    COLUMN_DTYPES_SALES = {"D1": "float64", "Volume": "float64", "Sales": "float64", "Price": "float64","Year":"object"}
    NON_NULL_COLUMNS_SALES = ["Market", "Region","Category","SubCategory","Brand","Year","Month"]  # Columns that must not have null values in Sales D0


    import streamlit as st
    import pandas as pd

    def validate_dataframe(df, df_name, required_columns, column_dtypes, non_null_columns):
        """Function to validate a DataFrame with user-controlled data type correction and session persistence."""
        
        # Initialize session state for validation tracking
        if f"{df_name}_validated" not in st.session_state:
            st.session_state[f"{df_name}_validated"] = False

        errors = []
        success_messages = []
        st.write(f"🔍 **Validating {df_name}...**")

        # 1️⃣ Check if required columns are present
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            errors.append(f"❌ Missing Columns: {', '.join(missing_columns)}")
        else:
            success_messages.append("✅ All required columns are present.")

        # 2️⃣ Check for null values in non-null columns  
        null_values_found = False  
        for col in non_null_columns:  
            if col in df.columns and df[col].isnull().sum() > 0:  
                null_values_found = True  
                missing_count = df[col].isnull().sum()  
                errors.append(f"⚠ Column '{col}' has {missing_count} missing values.")  

        # Only append the success message if no null values were found in any of the non-null columns  
        if not null_values_found:  
            success_messages.append("✅ All required columns do not have any missing values.")  

        # 3️⃣ Check data types
        dtype_mismatches = {}
        for col, expected_dtype in column_dtypes.items():
            if col in df.columns:
                actual_dtype = df[col].dtype
                if actual_dtype != expected_dtype:
                    errors.append(f"⚠ Column '{col}' has type {actual_dtype}, expected {expected_dtype}.")
                    dtype_mismatches[col] = expected_dtype

        # ✅ Append only once if there are no mismatches
        if not dtype_mismatches:
            success_messages.append("✅ All required columns are in the correct datatype.")
            
        # Store dtype mismatches in session state
        st.session_state[f"{df_name}_dtype_mismatches"] = dtype_mismatches

        # Display validation results
        if errors:
            st.error(f"❌ Validation Failed for {df_name}!")
            for error in errors:
                st.write(error)
            # st.session_state[f"{df_name}_validated"] = False  # Keep validation as failed
            return False
        # else:
        #     st.success(f"✅ {df_name} passed all validation checks!")
        #     st.session_state[f"{df_name}_validated"] = True
        #     return True
        # Display success messages
        for message in success_messages:
            st.write(message)

        st.success(f"✅ {df_name} passed all validation checks!")
        st.session_state[f"{df_name}_validated"] = True
        return True


    def apply_dtype_corrections(df, df_name):
        """Applies user-selected data type corrections."""
        
        if f"{df_name}_dtype_mismatches" not in st.session_state:
            return df  # No mismatches to fix

        dtype_mismatches = st.session_state[f"{df_name}_dtype_mismatches"]
        for col, expected_dtype in dtype_mismatches.items():
            try:
                df[col] = df[col].astype(expected_dtype)
                st.success(f"✅ Converted '{col}' to {expected_dtype}.")
            except Exception as e:
                st.error(f"❌ Failed to convert '{col}' to {expected_dtype}. Error: {e}")
        
        return df



    # Ensure session state is properly initialized
    if "media_validated" not in st.session_state:
        st.session_state["media_validated"] = False

    if "sales_validated" not in st.session_state:
        st.session_state["sales_validated"] = False




    with tab2:
        # st.write("### ✅ Validate D0 Files")

        if media_df is not None or sales_df is not None:

            # Check if files are uploaded before allowing validation
            if  media_df.empty and  sales_df.empty:
                st.error("❌ Please upload both Media D0 and Sales D0 files in Tab 1 before validation.")
            elif  media_df.empty:
                st.error("❌ Please upload the Media D0 file in Tab 1 before validation.")
            elif  sales_df.empty:
                st.error("❌ Please upload the Sales D0 file in Tab 1 before validation.")
            else:
                col3,col4 = st.columns(2)
                with col3:
                    if st.button("Validate Media D0"):
                        st.session_state["media_validated"] = validate_dataframe(
                            media_df, "Media D0", REQUIRED_COLUMNS_MEDIA, COLUMN_DTYPES_MEDIA, NON_NULL_COLUMNS_MEDIA
                        )
                        st.write(f"✅ Updated: media_validated = {st.session_state['media_validated']}")
                with col4:

                    if st.button("Validate Sales D0"):
                        st.session_state["sales_validated"] = validate_dataframe(
                            sales_df, "Sales D0", REQUIRED_COLUMNS_SALES, COLUMN_DTYPES_SALES, NON_NULL_COLUMNS_SALES
                        )
                        st.write(f"✅ Updated: sales_validated = {st.session_state['sales_validated']}")

            # st.rerun()
                # --- APPLY FIXES + AUTO RE-VALIDATE ---
                with col3:
                    if "media_validated" in st.session_state and not st.session_state["media_validated"]:
                        
                        if st.button("Apply Fixes to Media D0"):
                            media_df = apply_dtype_corrections(media_df, "Media D0")
                            # 🔄 Store the updated dataframe in session state
                            # st.session_state["media_df"] = media_df
                            # 🔄 Automatically re-validate after applying fixes
                            st.session_state["media_validated"] = validate_dataframe(
                                media_df, "Media D0", REQUIRED_COLUMNS_MEDIA, COLUMN_DTYPES_MEDIA, NON_NULL_COLUMNS_MEDIA
                            )
                            # st.write(f"🔄 Re-validation status: media_validated = {st.session_state['media_validated']}")
                            # st.write(f"🔍 DEBUG: media_validated = {st.session_state['media_validated']}")

                            # 🔄 Force rerun to refresh session state
                            # st.rerun()

                with col4:
                    if "sales_validated" in st.session_state and not st.session_state["sales_validated"]:
                        if st.button("Apply Fixes to Sales D0"):
                            sales_df = apply_dtype_corrections(sales_df, "Sales D0")
                            # 🔄 Automatically re-validate after applying fixes
                            st.session_state["sales_validated"] = validate_dataframe(
                                sales_df, "Sales D0", REQUIRED_COLUMNS_SALES, COLUMN_DTYPES_SALES, NON_NULL_COLUMNS_SALES
                            )
                            st.write(f"🔄 Re-validation status: sales_validated = {st.session_state['sales_validated']}")
                            
        # --- MOVE TO NEXT STEP ONLY IF BOTH FILES ARE VALIDATED ---
        if (
            "media_validated" in st.session_state and st.session_state["media_validated"] and
            "sales_validated" in st.session_state and st.session_state["sales_validated"]
        ):
            st.success("🎉 Both Media D0 and Sales D0 files are validated! You can proceed to the next step.")
            # if st.button("Proceed to Next Step"):
            #     st.write("👉 Moving to the next process...")

    ##########################################################################################################################################################################################
    ############################################################################################################################################################################################################
    ############################################################################################################################################################################################################
    ############################################################################################################################################################################################################
                

    def calculate_Brand_seasonality(data):
        # Check if weekly seasonality is feasible
        if data["Week"].isna().all() or data["Week"].nunique() <= 26:
            print("Data is not suitable for weekly seasonality. Calculating on a Monthly Basis.")
            result_market = data.groupby(['Market', 'Brand', 'Month'])[['Volume']].mean().reset_index()
            result_region = data.groupby(['Market', 'Region', 'Brand', 'Month'])[['Volume']].mean().reset_index()

        elif data["Week"].isna().any():
            raise ValueError("The 'Week' column contains partial NaN values. Please clean the data before proceeding.")

        else:
            # user_input = input("Would you like to calculate Weekly seasonality? (yes/no): ").strip().lower()
            # if user_input in ["yes", "y"]:
            #     # print("Calculating Weekly seasonality.")
            #     result_market = data.groupby(['Market', 'Brand', 'Week'])[['Volume']].mean().reset_index()
            #     result_region = data.groupby(['Market', 'Region', 'Brand', 'Week'])[['Volume']].mean().reset_index()
            # else:
            print("Default Monthly Seasonality")
            result_market = data.groupby(['Market', 'Brand', 'Month'])[['Volume']].mean().reset_index()
            result_region = data.groupby(['Market', 'Region', 'Brand', 'Month'])[['Volume']].mean().reset_index()

        # Rename columns
        result_market.rename(columns={"Volume": "Brand_seasonality"}, inplace=True)
        result_region.rename(columns={"Volume": "Region_Brand_seasonality"}, inplace=True)

        # Merge results back into the original data
        if 'Week' in result_market.columns:
            # data = pd.merge(data, result_market, on=['Market', 'Brand', 'Week'], how='left')
            # data = pd.merge(data, result_region, on=['Market', 'Region', 'Brand', 'Week'], how='left')
            data = pd.merge(data, result_market, on=['Market', 'Brand', 'Month'], how='left')
            data = pd.merge(data, result_region, on=['Market', 'Region', 'Brand', 'Month'], how='left')
        else:
            data = pd.merge(data, result_market, on=['Market', 'Brand', 'Month'], how='left')
            data = pd.merge(data, result_region, on=['Market', 'Region', 'Brand', 'Month'], how='left')

        return data

    def calculate_m_category_seasonality(volume_data):
        if volume_data["Week"].isna().all() or volume_data["Week"].nunique() <= 26:
            print("Data is not suitable for weekly Category seasonality. Calculating on a Monthly Basis.")

            # Monthly aggregation
            category_units = volume_data.groupby([
                'Market', 'Channel', 'Category', 'Year', 'Month'
            ]).agg({'Volume': 'sum'}).reset_index()
            category_units = category_units.rename(columns={"Volume": "category_units"})

            # Monthly seasonality at market level
            result_cat_market = category_units.groupby([
                'Market', 'Channel', 'Category', 'Month'
            ])[['category_units']].mean().reset_index()
            result_cat_market = result_cat_market.rename(columns={"category_units": "Market_Category_seasonality"})

        elif volume_data["Week"].isna().any():
            raise ValueError("The 'Week' column contains partial NaN values. Please clean the data before proceeding.")

        else:
            # user_input = input("Would you like to calculate Weekly seasonality? (yes/no): ").strip().lower()
            # if user_input in ["yes", "y"]:
            #     print("Calculating Weekly seasonality.")

            #     # Weekly aggregation
            #     category_units = volume_data.groupby([
            #         'Market', 'Channel', 'Category', 'Year', 'Week'
            #     ]).agg({'Volume': 'sum'}).reset_index()
            #     category_units = category_units.rename(columns={"Volume": "category_units"})

            #     result_cat_market = category_units.groupby([
            #         'Market', 'Channel', 'Category', 'Week'
            #     ])[['category_units']].mean().reset_index()
            #     result_cat_market = result_cat_market.rename(columns={"category_units": "Market_Category_seasonality"})

            # else:
            print("Defaulting to Monthly seasonality.")

            # Monthly aggregation
            category_units = volume_data.groupby([
                'Market', 'Channel', 'Region', 'Category', 'Year', 'Month'
            ]).agg({'Volume': 'sum'}).reset_index()
            category_units = category_units.rename(columns={"Volume": "category_units"})

            # Monthly seasonality at market and region levels
            result_cat_market = category_units.groupby([
                'Market', 'Channel', 'Category', 'Month'
            ])[['category_units']].mean().reset_index()
            result_cat_market = result_cat_market.rename(columns={"category_units": "Market_Category_seasonality"})

        # Merging both seasonality data into the original DataFrame
        volume_data = pd.merge(
            volume_data,
            result_cat_market,
            on=['Market', 'Channel', 'Category', 'Month'],
            how='left'
        )
        return volume_data

    def calculate_seasonality(volume_data):
        if volume_data["Week"].isna().all() or volume_data["Week"].nunique() <= 26:
            print("Data is not suitable for weekly Category seasonality. Calculating on a Monthly Basis.")

            # Monthly aggregation
            category_units = volume_data.groupby([
                'Market', 'Channel', 'Region', 'Category', 'Year', 'Month'
            ]).agg({'Volume': 'sum'}).reset_index()
            category_units = category_units.rename(columns={"Volume": "category_units"})

            result_cat_region = category_units.groupby([
                'Market', 'Channel', 'Region', 'Category', 'Month'
            ])[['category_units']].mean().reset_index()
            result_cat_region = result_cat_region.rename(columns={"category_units": "Region_Category_seasonality"})

        elif volume_data["Week"].isna().any():
            raise ValueError("The 'Week' column contains partial NaN values. Please clean the data before proceeding.")

        else:
            # user_input = input("Would you like to calculate Weekly seasonality? (yes/no): ").strip().lower()
            # if user_input in ["yes", "y"]:
            #     print("Calculating Weekly seasonality.")

            #     # Weekly aggregation
            #     category_units = volume_data.groupby([
            #         'Market', 'Channel', 'Region', 'Category', 'Year', 'Week'
            #     ]).agg({'Volume': 'sum'}).reset_index()
            #     category_units = category_units.rename(columns={"Volume": "category_units"})

            #     result_cat_region = category_units.groupby([
            #         'Market', 'Channel', 'Region', 'Category', 'Week'
            #     ])[['category_units']].mean().reset_index()
            #     result_cat_region = result_cat_region.rename(columns={"category_units": "Region_Category_seasonality"})
            # else:
            print("Defaulting to Monthly seasonality.")

            category_units = volume_data.groupby([
                'Market', 'Channel', 'Region', 'Category', 'Year', 'Month'
            ]).agg({'Volume': 'sum'}).reset_index()
            category_units = category_units.rename(columns={"Volume": "category_units"})

            result_cat_region = category_units.groupby([
                'Market', 'Channel', 'Region', 'Category', 'Month'
            ])[['category_units']].mean().reset_index()
            result_cat_region = result_cat_region.rename(columns={"category_units": "Region_Category_seasonality"})

        volume_data = pd.merge(
            volume_data,
            result_cat_region,
            on=['Market', 'Channel', 'Region', 'Category', 'Month'],
            how='left'
        )

        return volume_data
    def apply_kalman_filter(df, y_variable_col):
        initial_state_mean = df[y_variable_col].iloc[0]
        kf = KalmanFilter(
            initial_state_mean=initial_state_mean,
            transition_matrices=[1],
            observation_matrices=[1]
        )

        state_means, _ = kf.filter(df[y_variable_col].values)
        return state_means

    def apply_kalman_filter_to_data(volume_data, group_cols, value_col, output_col, kalman_function):
        volume_data[output_col] = np.nan
        grouped = volume_data.groupby(group_cols)

        for group_keys, group_df in grouped:
            if not group_df.empty:
                filtered_volume = kalman_function(group_df, y_variable_col=value_col)
                volume_data.loc[group_df.index, output_col] = filtered_volume
        return volume_data

    # Function to prepare Sales D0 based on user selections
    def prepare_sales_d1(df, apply_seasonality, apply_volume_index, apply_kalman, apply_market_share):
        
        # Apply seasonality calculations if selected
        if apply_seasonality:
            df = calculate_Brand_seasonality(df)
            df = calculate_m_category_seasonality(df)
            df = calculate_seasonality(df)

        # Apply Volume Index calculation if selected
        if apply_volume_index:
            df['Volume Index'] = np.nan
            for market in df['Market'].unique():
                df_market = df[df["Market"] == market]
                for region in df_market['Region'].unique():
                    df_region = df_market[df_market["Region"] == region]
                    for category in df_region['Category'].unique():
                        df_category = df_region[df_region["Category"] == category]
                        for sub_category in df_category['SubCategory'].unique():
                            df_sub_category = df_category[df_category["SubCategory"] == sub_category]
                            for brand in df_sub_category['Brand'].unique():
                                df_brand = df_sub_category[df_sub_category["Brand"] == brand]
                                volume_index = df_brand['Volume'] / df_brand['Volume'].mean()
                                df.loc[df_brand.index, "Volume Index"] = volume_index * 100

        # Sorting Data
        df = df.sort_values(by=['Region', 'Year', 'Month'], ascending=[True, True, True])

        # Apply Kalman Filter if selected
        if apply_kalman:
            df = apply_kalman_filter_to_data(df, group_cols=['Market', 'Region', 'Category', 'SubCategory', 'Brand'], value_col='Volume', output_col='Filtered Volume', kalman_function=apply_kalman_filter)
            if apply_volume_index:  # Only apply if Volume Index was created
                df = apply_kalman_filter_to_data(df, group_cols=['Market', 'Region', 'Category', 'SubCategory', 'Brand'], value_col='Volume Index', output_col='Filtered Volume Index', kalman_function=apply_kalman_filter)

        # Apply Market Share Calculation if selected
        if apply_market_share:
            df["Total Market Volume"] = df.groupby(["Market", "Region", "Category", "SubCategory", "Year", "Month"])['Volume'].transform('sum')
            df['Market Share Units'] = df['Volume'] / df['Total Market Volume']

        return df

    # Function to process Media D1
    def prepare_media_d1(df, group_by_cols, agg_cols, agg_funcs, pivot_on):
        """Aggregate media data and create a pivot table."""
        agg_dict = {col: func for col, func in zip(agg_cols, agg_funcs)}

        # Step 1: Aggregate Data
        grouped_df = df.groupby(group_by_cols).agg(agg_dict).reset_index()

        # Step 2: Pivot Data (if selected)
        if pivot_on and pivot_on in df.columns:
            # Use the same aggregation function for pivoted values
            pivot_aggfunc = {col: agg_dict[col] for col in agg_dict.keys()}
            
            pivoted_df = grouped_df.pivot_table(
                index=index_cols,
                columns=pivot_on,
                values=list(agg_dict.keys()),
                aggfunc=pivot_aggfunc  # Apply selected functions dynamically
            )

            # Flatten MultiIndex columns
            pivoted_df.columns = [f"{val[1]}_{val[0]}" if val[1] else val[0] for val in pivoted_df.columns]
            pivoted_df = pivoted_df.reset_index()
            return pivoted_df
        else:
            return grouped_df

    # # Define a function to determine the fiscal year
    # def get_fiscal_year(row):
    #     month = row['Month']
    #     year = row['Year']
        
    #     # Define the months range for the fiscal year
    #     if month in ['July', 'August', 'September', 'October', 'November', 'December']:
    #         fiscal_year = f"FY{str(year + 1)[-2:]}"
    #     else:
    #         fiscal_year = f"FY{str(year)[-2:]}"
        
    #     return fiscal_year
    
    # # Let user select fiscal year start month
    # fy_start_month = st.selectbox(
    #     "Select Fiscal Year Starting Month",
    #     options=['April', 'July', 'January', 'October'],  # Common fiscal year starts
    #     index=1,  # Default to July
    #     help="The fiscal year will be named after the year it ends in (e.g., FY23 for fiscal year ending in 2023)"
    # )

    # # Define the function with correct fiscal year naming
    # def get_fiscal_year(row, start_month):
    #     month = row['Month']
    #     year = row['Year']
        
    #     months_order = ['January', 'February', 'March', 'April', 'May', 'June',
    #                 'July', 'August', 'September', 'October', 'November', 'December']
        
    #     start_idx = months_order.index(start_month)
        
    #     # Determine if month is in same fiscal year or next
    #     if months_order.index(month) >= start_idx:
    #         # Months after start month (including start month) - same fiscal year end
    #         fiscal_year = f"FY{str(year + 1)[-2:]}"
    #     elif months_order == ['January']:
    #         # Months before start month - previous fiscal year end
    #         fiscal_year = f"FY{str(year)[-2:]}"
    #     else:
    #         fiscal_year = f"FY{str(year)[-2:]}"
        
    #     return fiscal_year
    def get_fiscal_year(row, start_month):
        month = row['Month']
        year = row['Year']

        months_order = ['January', 'February', 'March', 'April', 'May', 'June',
                        'July', 'August', 'September', 'October', 'November', 'December']

        start_idx = months_order.index(start_month)
        current_idx = months_order.index(month)

        if start_month == 'January':
            # Fiscal year is same as calendar year
            fiscal_year = f"FY{str(year)[-2:]}"
        elif current_idx >= start_idx:
            # Month is in the same fiscal year (which ends next year)
            fiscal_year = f"FY{str(year + 1)[-2:]}"
        else:
            # Month is before start month → previous fiscal year
            fiscal_year = f"FY{str(year)[-2:]}"
        
        return fiscal_year


    with tab3:
        # st.write("## 🏗️ D1 Preparation")

        # # Debugging statements to check session state
        # st.write(f"🔍 Debug: media_validated = {st.session_state.get('media_validated', False)}")
        # st.write(f"🔍 Debug: sales_validated = {st.session_state.get('sales_validated', False)}")
        if media_df is not None or sales_df is not None:

            if media_df.empty or sales_df.empty:
                st.error("❌ Please upload both Media D0 and Sales D0 files in Tab 1 before validation.")

            # ❌ Corrected: If validation has NOT happened, show error
            elif not st.session_state.get("media_validated", False) or not st.session_state.get("sales_validated", False):
                st.error("❌ Please validate both Sales D0 and Media D0 in Tab 2 before proceeding to D1 Preparation!")

            else:
                st.success("✅ Both datasets are validated! You can proceed with D1 preparation.")
                # st.write("### Start Preparing D1...")

                col1, col2 = st.columns(2)
                with col2:

                    st.write("### Sales D1 Preparation")
                    # sales_file = st.session_state["sales_df"]
                    # --- SALES D1 PREPARATION ---
                    # if "sales_file_uploaded" in st.session_state:
                    try:
                        sales_file = st.session_state["sales_df"]
                        # if sales_file.name.endswith(".csv"):
                        #     df_sales = pd.read_csv(sales_file)
                        # else:
                        #     df_sales = pd.read_excel(sales_file)
                        
                        # st.success("Sale D0 uploaded successfully!")

                        df_sales = sales_file.fillna(0)
                        with st.expander("Options to prepare Sales D1"):

                            # User Selection for Processing Steps
                            apply_seasonality = st.checkbox("Apply Seasonality Calculation", value=True)
                            apply_volume_index = st.checkbox("Create Volume Index Column", value=True)
                            apply_kalman = st.checkbox("Apply Kalman Filter", value=False)
                            apply_market_share = st.checkbox("Calculate Market Share", value=True)

                        # Button to prepare Sales D0
                        if st.button("Prepare Sales D1"):
                            sales_d1 = prepare_sales_d1(df_sales, apply_seasonality, apply_volume_index, apply_kalman, apply_market_share)
                            st.session_state.sales_d1 = sales_d1  # Store processed sales_d1
                            st.success("Sales D0 preparation complete!")
                        if "sales_d1" in st.session_state:
                            with st.expander("Prepared Sales D1", expanded=True):
                                st.dataframe(st.session_state.sales_d1)  # Display the prepared data

                    except Exception as e:
                        st.error(f"Error reading file: {e}")

                with col1:
                    st.write("### Media D1 Preparation")


                    # --- MEDIA D1 PREPARATION ---
                    try:
                        media_file = st.session_state["media_df"]
                        # if media_file.name.endswith(".csv"):
                        #     media_data = pd.read_csv(media_file)
                        # else:
                        #     media_data = pd.read_excel(media_file)

                        # st.session_state.media_d0 = media_data.fillna(0)  # Store Media D0
                        # st.success("Media D0 uploaded successfully!")
                        media_data = media_file.fillna(0)

                        with st.expander("Options to prepare Media D1"):
                            # User selects columns to group by
                            group_by_cols = st.multiselect("Select Columns to Group By", options=media_data.columns, default=['Market', 'Channel', 'Region', 'Category', 'SubCategory', 'Brand',
                            'Variant',  'PackType', 'PPG', 'PackSize', 'Year', 'Month', "Week", 'Media Category', 'Media Subcategory'])
                            
                            # User selects index columns (for pivot table)
                            index_cols = st.multiselect("Select Index Columns (for Pivot Table)", 
                                                        options=group_by_cols, 
                                                        default=['Market', 'Channel', 'Region', 'Category', 'SubCategory', 'Brand',
                                                                'Year', 'Month'])

                            # User selects columns to aggregate
                            agg_cols = st.multiselect("Select Columns to Aggregate", options=media_data.select_dtypes(include=['number']).columns)#, default=["Unique_Reach", "Amount_Spent"])

                            # User selects aggregation function for each column
                            agg_funcs = []
                            for col in agg_cols:
                                func = st.selectbox(f"Select Aggregation Function for {col}", options=["sum", "mean", "min", "max"], index=0, key=f"agg_{col}")
                                agg_funcs.append(func)

                            # Find the index of 'Media Subcategory' if it exists in columns
                            columns_list = list(media_data.columns)
                            default_index = columns_list.index('Media Subcategory') + 1 if 'Media Subcategory' in columns_list else 0

                            # User selects the pivot column
                            pivot_on = st.selectbox(
                                "Select Column to Pivot On",
                                options=["None"] + columns_list,
                                index=default_index  # This sets the default selection
                            )

                            # User selects the pivot column
                            # pivot_on = st.selectbox("Select Column to Pivot On", options=["None"] + list(media_data.columns), index=0,default=['Media Subcategory'])

                        # Button to process Media D1
                        if st.button("Prepare Media D1"):
                            if group_by_cols and agg_cols:
                                pivot_on = None if pivot_on == "None" else pivot_on
                                media_d1 = prepare_media_d1(media_data, group_by_cols, agg_cols, agg_funcs, pivot_on)
                                st.session_state.media_d1 = media_d1  # Store processed Media D1
                                st.success("Media D1 preparation complete!")
                            
                                # st.write("Prepared Media D1:")
                                # st.dataframe(st.session_state.media_d1)  # Display the processed data
                            else:
                                st.error("Please select at least one column to group by and one column to aggregate.")
                        if "media_d1" in st.session_state:
                            with st.expander("Prepared Media D1", expanded=True):
                                st.dataframe(st.session_state.media_d1)  # Display the processed data

                    except Exception as e:
                        st.error(f"Error reading Media D0 file: {e}")


            st.markdown(
            """ 
            <div style="height: 1px; background-color: black; margin: 15px 0;"></div>
            """, 
            unsafe_allow_html=True
            )  

            st.write("### Merge Sales D1 and Media D1")

        # Check if Sales D1 and Media D1 are available
        if "sales_d1" in st.session_state and "media_d1" in st.session_state:
            sales_data = st.session_state.sales_d1
            media_data = st.session_state.media_d1

            # User selects columns for merging
            common_columns = list(set(sales_data.columns) & set(media_data.columns))  # Find common columns

            col7, col8 = st.columns(2)
            with col7:

                merge_keys = st.multiselect("Select Columns for Merging Sales D1 and Media D1", options=common_columns, 
                                        default=['Market', 'Channel', 'Region', 'Category', 'SubCategory', 'Brand', 'Year', 'Month'])
            with col8:
                # Let user select fiscal year start month
                fy_start_month = st.selectbox(
                    "Select Fiscal Year Starting Month",
                    options=['April', 'July', 'January', 'October'],  # Common fiscal year starts
                    index=1,  # Default to July
                    help="The fiscal year will be named after the year it ends in (e.g., FY23 for fiscal year ending in 2023)"
                )

            # Button to merge Sales D1 and Media D1
            if st.button("Merge Sales D1 and Media D1"):
                if merge_keys:
                    final_data_for_model = pd.merge(sales_data, media_data, on=merge_keys, how='left')
                    # Convert month numbers to month names
                    final_data_for_model['Month'] = final_data_for_model['Month'].apply(lambda x: calendar.month_name[x])
                    # Apply the function to each row in the DataFrame
                    final_data_for_model['Fiscal Year'] = final_data_for_model.apply(
                                                                                        lambda row: get_fiscal_year(row, fy_start_month),
                                                                                        axis=1
                                                                                    )
                    final_data_for_model = final_data_for_model.fillna(0)
                    # Store the merged dataset
                    st.session_state.final_data_for_model = final_data_for_model

                    st.success("Sales D1 and Media D1 merged successfully!")
                    st.write("Final Data for Modeling:")
                    st.dataframe(final_data_for_model)
                else:
                    st.error("Please select at least one column for merging.")



    ##########################################################################################################################################################################################
    ##########################################################################################################################################################################################
    ##########################################################################################################################################################################################



if selected == "EXPLORE":


    import streamlit as st
    import pandas as pd
    import numpy as np
    import matplotlib.pyplot as plt
    from sklearn.preprocessing import StandardScaler, MinMaxScaler
    import plotly.graph_objects as go
    import io
    import plotly.express as px


    # # Restrict access
    # if "authenticated" not in st.session_state or not st.session_state.authenticated:
    #     st.error("Unauthorized access! Please log in from the main page.")
    #     st.stop()  # 🚫 Stop further execution if user is not logged in

    # st.title("EDA")
    # st.markdown(
    #             """ 
    #             <div style="height: 3px; background-color: black; margin: 15px 0;"></div>
    #             """, 
    #             unsafe_allow_html=True
    #             )


    uploaded_file = st.sidebar.file_uploader("Upload your dataset for EDA", type=["csv", "xlsx"])

    # # Function to format numbers in Millions (M) or Thousands (K)
    # def format_value(val):
    #     if val >= 1_000_000:
    #         return f"{val/1_000_000:.1f}M"  # Convert to Millions with 1 decimal
    #     elif val >= 1_000:
    #         return f"{val/1_000:.1f}K"  # Convert to Thousands with 1 decimal
    #     else:
    #         return f"{val:.1f}"  # Show normal value with 1 decimal

    if uploaded_file:
        try:
            # Load the dataset
            if uploaded_file.name.endswith(".csv"):
                df = pd.read_csv(uploaded_file,sheet_name = "Sheet1")
            else:
                df = pd.read_excel(uploaded_file, sheet_name="Sheet1")

        except Exception as e:
            st.error(f"Error loading file: {e}")

    def create_date_column(df):
        """
        Create Date column from Year, Month, and Week (if available) with proper week handling.
        Week numbers follow ISO standard (1-52 or 53).
        """
        # Validate and clean Year
        df["Year"] = pd.to_numeric(df["Year"], errors="coerce")
        df = df.dropna(subset=["Year"])
        df["Year"] = df["Year"].astype(int)
        
        # Check if Week column exists and is valid
        if 'Week' in df.columns:
            # Clean Week column
            df["Week"] = pd.to_numeric(df["Week"], errors="coerce")
            df = df.dropna(subset=["Week"])
            df["Week"] = df["Week"].astype(int)
            
            # Validate week numbers (1-52 or 53)
            invalid_weeks = ~df["Week"].between(1, 53)
            if invalid_weeks.any():
                st.warning(f"Found {invalid_weeks.sum()} rows with invalid week numbers (not 1-53). These will use month-only dates.")
            
            try:
                # For rows with valid weeks (1-53)
                valid_weeks = df["Week"].between(1, 53)
                
                # Create ISO week dates (Monday as first day of week)
                df.loc[valid_weeks, "Date"] = (
                    df.loc[valid_weeks, "Year"].astype(str) + "-W" + 
                    df.loc[valid_weeks, "Week"].astype(str).str.zfill(2) + "-1"
                )
                df.loc[valid_weeks, "Date"] = pd.to_datetime(
                    df.loc[valid_weeks, "Date"], 
                    format="%Y-W%W-%w", 
                    errors="coerce"
                )
                
                # For rows with invalid weeks or failed conversions, fall back to month
                fallback_mask = valid_weeks & df["Date"].isna()
                if fallback_mask.any():
                    st.warning(f"Couldn't convert {fallback_mask.sum()} week-based dates. Falling back to month.")
            except Exception as e:
                st.warning(f"Week-to-date conversion failed: {str(e)}. Falling back to month.")
        
        # For all rows without week dates, use Year-Month (first day of month)
        month_only_mask = ~df["Date"].notna() if 'Date' in df.columns else pd.Series(True, index=df.index)
        if month_only_mask.any():
            df.loc[month_only_mask, "Date"] = pd.to_datetime(
                df.loc[month_only_mask, "Year"].astype(str) + "-" + 
                df.loc[month_only_mask, "Month"], 
                format="%Y-%B", 
                errors="coerce"
            )
        
        # Final cleanup
        df = df.dropna(subset=["Date"])
        df["Date"] = df["Date"].dt.normalize()  # Remove time component
        
        return df

    # # Initialize df as None at the start (optional but good practice)
    # df = None

    # if "final_data_for_model" in st.session_state:
    #     df = st.session_state.final_data_for_model

    # First check if df exists and is not empty
    if df is not None and not df.empty:
        # Function to format values as M (millions) or K (thousands)
        def format_value(x):
            return f"{x / 1e6:.1f}M" if x >= 1e6 else f"{x / 1e3:.1f}K"

        # Ensure the dataset has a 'Fiscal Year' column
        if "Fiscal Year" not in df.columns:
            st.error("The uploaded dataset must contain a 'Fiscal Year' column.")
        else:
            # Step 1: Let the user select one or more Fiscal Years
            fiscal_years = df["Fiscal Year"].dropna().unique()
            selected_years = st.multiselect("Select Fiscal Year(s) for EDA", sorted(fiscal_years),default=fiscal_years)

            if selected_years:
                # Filter dataset for the selected Fiscal Years
                df_filtered = df[df["Fiscal Year"].isin(selected_years)]
                if "Date" not in df_filtered.columns:
                    df_filtered["Date"] = pd.to_datetime(df_filtered["Year"].astype(str) + "-" + df_filtered["Month"], format="%Y-%B")

                # # Apply to your DataFrames
                # if 'df_filtered' in locals() or 'df_filtered' in globals():
                #     try:
                #         df_filtered = create_date_column(df_filtered.copy())
                #     except Exception as e:
                #         st.error(f"Error processing df_filtered: {str(e)}")

                st.write(f"#### EDA for Fiscal Year(s) {', '.join(map(str, selected_years))}")
                with st.expander("View Filtered Dataset"):
                    st.dataframe(df_filtered, hide_index=True)
                # st.write("Preview of the filtered dataset:")
                # st.dataframe(df_filtered.head(), hide_index=True)

                # Show DataFrame Shape
                st.write(f"#### **Shape of Dataset:** `{df_filtered.shape[0]}` rows × `{df_filtered.shape[1]}` columns")
            else:
                st.warning("Please select at least one Fiscal Year to view the EDA.")
                # # Store selection in session state
                # if "show_barplot" not in st.session_state:
                #     st.session_state.show_barplot = False

                # if st.button("Show Bar Plot"):
                #     st.session_state.show_barplot = True
        # Create Cluster-level aggregated data

        # df_filtered["Date"] = pd.to_datetime(df_filtered["Year"].astype(str) + "-" + df_filtered["Month"], format="%Y-%B")  "Date", 
        all_india_df = df_filtered.groupby(['Market', 'Brand','Year', 'Month', "Fiscal Year"], as_index=False).agg(
            {**{col: 'sum' for col in df_filtered.select_dtypes(include='number').columns 
                if col not in ['Channel', 'Variant', 'PackType', 'PPG', 'PackSize', 'Week', "D1"]},
            'D1': 'sum'}
        ).reset_index()

        # if 'all_india_df' in locals() or 'all_india_df' in globals():
        #     try:
        #         all_india_df = create_date_column(all_india_df.copy())
        #     except Exception as e:
        #         st.error(f"Error processing all_india_df: {str(e)}")

        # Add Price column
        # all_india_df["Date"] = pd.to_datetime(all_india_df["Year"].astype(str) + "-" + all_india_df["Month"], format="%Y-%B")
        # Ensure Year is numeric and valid
        all_india_df["Year"] = pd.to_numeric(all_india_df["Year"], errors="coerce")

        # Drop rows with invalid Year values
        all_india_df = all_india_df.dropna(subset=["Year"])

        # Convert Year to integer
        all_india_df["Year"] = all_india_df["Year"].astype(int)

        if 'Date' not in all_india_df.columns:

            # Convert Month & Year to Date
            all_india_df["Date"] = pd.to_datetime(
                all_india_df["Year"].astype(str) + "-" + all_india_df["Month"], 
                format="%Y-%B", 
                errors="coerce"
            )

        # Drop rows where Date couldn't be parsed
        all_india_df = all_india_df.dropna(subset=["Date"])

        

        all_india_df["Price"] = all_india_df["Sales"] / all_india_df["Volume"]
        all_india_df["Region"] = "Cluster"

        # Step 2: Select Region or Cluster
        # st.markdown('<p style="font-size:15px; color:Black; font-weight:bold;">Select Data Source:</p>', unsafe_allow_html=True)
        data_option = st.radio("##### Select Data Source", ["Region", "Cluster"], key="data_source_radio")  # ✅ Added key

        # Step 3: Select Region if Region is chosen
        if data_option == "Region":
            available_regions = df_filtered["Region"].unique().tolist()
            available_brands = df_filtered["Brand"].unique().tolist()
            st.markdown('<p style="font-size:15px; color:black; font-weight:bold;">Select a Region:</p>', unsafe_allow_html=True)
            col9, col10 = st.columns(2)
            with col9:
                selected_region = st.selectbox("", available_regions, key="region_selector")  # ✅ Added key
            with col10:
                selected_brand = st.selectbox("Select a Brand:", available_brands, key="brand_selector")  # ✅ Added key
            selected_df = df_filtered[(df_filtered["Region"] == selected_region) & (df_filtered["Brand"] == selected_brand)]
            # selected_df = df_filtered[df_filtered["Region"] == selected_region]
            st.write(f"Using **Region-Level Data** for {selected_region}")
        else:
            selected_df = all_india_df
            st.write("Using **Cluster-Level Data** for the Chart.")

        # Remove columns where all values are zero
        selected_df = selected_df.loc[:, (selected_df != 0).any(axis=0)]


        st.markdown(
            """ 
            <div style="height: 3px; background-color: black; margin: 15px 0;"></div>
            """, 
            unsafe_allow_html=True
            )


        st.markdown(
                        """
                        <style>
                            div.stTabs button {
                                flex-grow: 1;
                                text-align: center;
                            }
                        </style>
                        """,
                        unsafe_allow_html=True
                    )


        st.markdown("""
            <style>


            /* Make the tab text bolder */
            div.stTabs button div p {
                font-weight: 900 !important; /* Maximum boldness */
                font-size: 18px !important; /* Slightly larger text */
                color: black !important; /* Ensuring good contrast */
            }
            </style>
        """, unsafe_allow_html=True)

        # col1,col2,col3,col4,col5 = st.columns(5)
        tab1,tab2,tab3,tab4,tab5,tab6 = st.tabs(["Bar Plot","Summary Table","Percentage Change","Time Series Plot","Pie Chart","Correlation Matrix"])

        ### barplot Table -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
        with tab1:
        #     if st.button("Show Bar Plot"):
        #         st.session_state.active_plot = "barplot"
        # # Display the selected plot
        # if st.session_state.active_plot == "barplot":
            st.write("### Bar Plot")
            numerical_columns = df_filtered.select_dtypes(include=['number']).columns.tolist()

            # Persist selection in session state
            selected_columns = st.multiselect(
                "Select columns for Bar Chart", 
                numerical_columns,
                default=["Volume"]  # Default selection
                # default=st.session_state.selected_bar_columns  # Restore previous selection
            )

            # # Update session state when user makes a selection
            # if selected_columns:
            #     st.session_state.selected_bar_columns = selected_columns

            # if st.session_state.selected_bar_columns:
            # Melt the DataFrame for visualization
            df_melted = selected_df.melt(id_vars=["Fiscal Year", "Region"], value_vars=selected_columns, 
                                    var_name="Metric", value_name="Value")
            df_melted = df_melted.groupby(["Fiscal Year", "Region", "Metric"], as_index=False)["Value"].sum()

            # Apply formatting
            df_melted["Formatted_Value"] = df_melted["Value"].apply(format_value)

            # Function to clean metric names
            def clean_metric_name(metric):
                words = metric.replace("_", " ").split()  
                return " ".join(words[:2])  # Keep only the first two words
            
            df_melted["Metric"] = df_melted["Metric"].apply(clean_metric_name)  

            # Plot the bar chart
            fig = px.bar(df_melted, 
                        x="Value", 
                        y="Metric", 
                        color="Fiscal Year", 
                        barmode="group",
                        facet_col="Region",  
                        text=df_melted["Formatted_Value"],  
                        title="Comparison of Selected Metrics Across Fiscal Years & Regions")

            st.plotly_chart(fig)
            # elif st.session_state.show_barplot:
            #     st.warning("Please select at least one column for the bar chart.")




        # elif st.session_state.active_plot == "summary":
        with tab2:
            st.write("### Summary Table")
            month_order = ["July", "August", "September", "October", "November", "December",
                        "January", "February", "March", "April", "May", "June"]

            # Get unique values for selection
            if "Region" in df_filtered.columns:
                # region_options = df_filtered["Region"].unique()
                # column_options = [col for col in df.columns if col not in ["Region", "Month", "Fiscal Year"]]
                column_options = [col for col in df.select_dtypes(include=[np.number]).columns]


                # Ensure a valid default index
                # default_index = column_options.index(st.session_state.selected_summary_columns) if st.session_state.selected_summary_columns in column_options else 0

                # # Persist selection in session state
                # selected_columns = st.selectbox(
                #     "Select columns for Summary Table", 
                #     column_options, 
                #     # index=default_index  # Correct way to set default selection
                #     default = ["Volume"]
                # )
                # Find index of "Volume" in column_options if it exists
                default_index = column_options.index("Volume") if "Volume" in column_options else 0

                # Single selection
                selected_column = st.selectbox(
                    "Select column for Summary Table", 
                    column_options, 
                    index=default_index  # Correct way to set default selection
                )

                # # # Update session state only if the selection changes
                # if selected_columns != st.session_state.selected_summary_columns:
                #     st.session_state.selected_summary_columns = selected_columns

                # Pivot Data to Get Summary
                summary_table = selected_df.pivot_table(
                    index="Month", columns="Fiscal Year", values=selected_column, aggfunc="sum"
                ).reindex(month_order)  # Ensuring months are in correct order

                # Format numbers for readability
                formatted_table = summary_table.applymap(lambda x: f"{x:,.0f}" if pd.notna(x) else "-")

                # Display table
                st.data_editor(formatted_table, use_container_width=True)







        # elif st.session_state.active_plot == "percentage_change":
        with tab3:
            st.write("### Percentage Change")
            # def calculate_percentage_change(df, selected_years, selected_columns):
            #     """
            #     Function to calculate the percentage change of selected numerical columns 
            #     between the selected fiscal year(s) and their previous fiscal year.
                
            #     Args:
            #     df (DataFrame): The original dataset containing 'Fiscal Year' and 'Region' columns.
            #     selected_years (list): List of selected fiscal years.
            #     selected_columns (list): List of selected numerical columns.

            #     Returns:
            #     DataFrame: A table showing the percentage change for each region.
            #     """
            #     # Extract the numeric part from fiscal year strings and adjust for previous year comparison
            #     previous_years = [f"FY{int(fy[2:]) - 1}" for fy in selected_years]
            #     df_previous = selected_df[selected_df["Fiscal Year"].isin(previous_years)]

            #     if not df_previous.empty:
            #         # Aggregate selected columns by Fiscal Year and Region
            #         df_current = selected_df[selected_df["Fiscal Year"].isin(selected_years)].groupby(["Fiscal Year", "Region"])[selected_columns].sum().reset_index()
            #         df_previous_grouped = df_previous.groupby(["Fiscal Year", "Region"])[selected_columns].sum().reset_index()

            #         # Adjust previous fiscal years to align with the selected fiscal years
            #         df_previous_grouped["Fiscal Year"] = df_previous_grouped["Fiscal Year"].apply(lambda x: f"FY{int(x[2:]) + 1}")

            #         # Merge with the current year data
            #         df_comparison = df_current.merge(df_previous_grouped, on=["Fiscal Year", "Region"], suffixes=("", "_Previous"))

            #         # Calculate % change
            #         for col in selected_columns:
            #             prev_col = col + "_Previous"
            #             df_comparison[f"% Change in {col}"] = ((df_comparison[col] - df_comparison[prev_col]) / df_comparison[prev_col]) * 100
            #             df_comparison[f"% Change in {col}"] = df_comparison[f"% Change in {col}"].apply(lambda x: f"{x:.1f}%" if pd.notnull(x) else "N/A")

            #         # Select relevant columns for display
            #         change_columns = ["Fiscal Year", "Region"] + [f"% Change in {col}" for col in selected_columns]
            #         df_comparison = df_comparison[change_columns]

            #         return df_comparison
            #     else:
            #         st.warning("No previous fiscal year data available for comparison.")
            #         return None

            # # Example usage inside Streamlit
            # st.write("### 📊 Percentage Change from Previous Fiscal Year")


            # # Get unique fiscal years and numerical columns
            # fiscal_years = df_filtered["Fiscal Year"].dropna().unique()
            # numerical_columns = df_filtered.select_dtypes(include=['number']).columns.tolist()



            # # Fiscal year selection with session state
            # selected_years = st.multiselect(
            #     "Select Fiscal Year(s) for Comparison", 
            #     sorted(fiscal_years),
            #     default=fiscal_years[1]  # Use valid stored selections
            #     # default=valid_selected_fiscal_years  # Use valid stored selections
            # )


            # # Columns selection with session state
            # selected_columns = st.multiselect(
            #     "Select Columns for % Change Calculation", 
            #     numerical_columns,
            #     default=["Volume"]  # Use valid stored selections
            #     # default=valid_selected_columns  # Use valid stored selections
            # )

            # # Check if selections are valid before calculations
            # if selected_years and selected_columns:
            #     df_percentage_change = calculate_percentage_change(df_filtered, selected_years, selected_columns)
                
            #     if df_percentage_change is not None:
            #         st.dataframe(df_percentage_change)


        # elif st.session_state.active_plot == "time_series":
        with tab4:
            # st.write("### Time Series Plot")
            # # Get numerical columns
            # numeric_columns = selected_df.select_dtypes(include=['number']).columns.tolist()


            # # User selects columns for each axis
            # col1, col2 = st.columns(2)
            # with col1:
            #     y1_column = st.selectbox("Select Column for Primary Y-Axis", selected_df.select_dtypes(include=['number']).columns, index=0, key="y1_column")

            # with col2:
            #     y2_column = st.selectbox("Select Column for Secondary Y-Axis", selected_df.select_dtypes(include=['number']).columns, index=1 if len(selected_df.columns) > 1 else 0, key="y2_column")
            #     # y2_column = st.selectbox("Select Column for Secondary Y-Axis", selected_df.select_dtypes(include=['number']).columns,
            #     #                           index=1 if len(selected_df.columns) > 1 else 0, key="y2_column")


            # ts_df = selected_df[["Date", y1_column, y2_column]].copy()
            # ts_df = ts_df[ts_df[y1_column]!=0]# & ts_df[y2_column]!=0]  # Filter out zero values
            # ts_df = ts_df.sort_values(by="Date")  # Sort by date
            # # st.write(ts_df)

            # if y1_column and y2_column:
            #     fig = go.Figure()

            #     # Add primary y-axis line
            #     fig.add_trace(go.Scatter(
            #         x=ts_df["Date"],
            #         y=ts_df[y1_column],
            #         mode="lines+markers",
            #         name=y1_column,
            #         yaxis="y1"
            #     ))

            #     # Add secondary y-axis line
            #     fig.add_trace(go.Scatter(
            #         x=ts_df["Date"],
            #         y=ts_df[y2_column],
            #         mode="lines+markers",
            #         name=y2_column,
            #         yaxis="y2"
            #     ))

            #     # Layout settings
            #     fig.update_layout(
            #         title="Dual-Axis Line Chart",
            #         xaxis=dict(title="Date", type="date"),
            #         yaxis=dict(
            #             title=y1_column,
            #             side="left",
            #             showgrid=False
            #         ),
            #         yaxis2=dict(
            #             title=y2_column,
            #             overlaying="y",
            #             side="right",
            #             showgrid=False
            #         ),
            #         legend=dict(x=0.05, y=1.1),
            #     )

            #     st.plotly_chart(fig, use_container_width=True)
            import plotly.graph_objects as go
            import streamlit as st

            st.write("### Time Series Plot")

            # Get numerical columns
            numeric_columns = selected_df.select_dtypes(include=['number']).columns.tolist()

            # User selects multiple columns for each Y-axis
            col1, col2 = st.columns(2)
            with col1:
                y1_columns = st.multiselect(
                    "Select Column(s) for Primary Y-Axis",
                    numeric_columns,
                    default=[numeric_columns[0]] if numeric_columns else []
                )

            with col2:
                y2_columns = st.multiselect(
                    "Select Column(s) for Secondary Y-Axis",
                    numeric_columns,
                    default=[numeric_columns[1]] if len(numeric_columns) > 1 else []
                )

            # Prepare dataframe
            all_cols = ["Date"] + y1_columns + y2_columns
            ts_df = selected_df[all_cols].copy()
            ts_df = ts_df.sort_values(by="Date")

            # Create plot
            if y1_columns or y2_columns:
                fig = go.Figure()

                # Add traces for primary Y-axis
                for col in y1_columns:
                    fig.add_trace(go.Scatter(
                        x=ts_df["Date"],
                        y=ts_df[col],
                        mode="lines+markers",
                        name=f"{col} (Primary)",
                        yaxis="y1"
                    ))

                # Add traces for secondary Y-axis
                for col in y2_columns:
                    fig.add_trace(go.Scatter(
                        x=ts_df["Date"],
                        y=ts_df[col],
                        mode="lines+markers",
                        name=f"{col} (Secondary)",
                        yaxis="y2"
                    ))

                # Layout settings
                fig.update_layout(
                    title="Dual-Axis Multi-Variable Line Chart",
                    xaxis=dict(title="Date", type="date"),
                    yaxis=dict(
                        title="Primary Y-Axis",
                        side="left",
                        showgrid=False
                    ),
                    yaxis2=dict(
                        title="Secondary Y-Axis",
                        overlaying="y",
                        side="right",
                        showgrid=False
                    ),
                    legend=dict(x=0.05, y=1.1),
                )

                st.plotly_chart(fig, use_container_width=True)




        # elif st.session_state.active_plot == "pie_chart":
        with tab5:
            st.write("### Pie Chart")

            # Allow the user to select columns for the pie chart  
            available_columns = selected_df.select_dtypes(include='number').columns.tolist()  
            # selected_columns = st.multiselect(  
            #     "Select columns for the pie chart",   
            #     available_columns,   
            #     key="column_selector"  # Default selection  
            # )  
            # # Filter columns that start with "TV"
            default_tv_columns = [col for col in available_columns if col.startswith("TV")]

            # Streamlit multiselect with default TV columns selected
            selected_columns = st.multiselect(  
                "Select columns for the pie chart",   
                available_columns,   
                default=default_tv_columns,  # <-- Default selection here
                key="column_selector"
            )


            # Step 4: Create Pie Chart for Selected Columns
            if selected_columns:
                # Calculate the sum of each selected column
                column_sums = selected_df[selected_columns].sum()

                # Prepare data for the pie chart
                pie_data = pd.DataFrame({
                    'Column': column_sums.index,
                    'Sum': column_sums.values
                })

                # Choose a color palette (Options: Blues, Greens, Oranges, Purples, etc.)
                color_palette = px.colors.sequential.Purp  # Change this to Greens, Oranges, Purples, etc.

                # Generate shades dynamically based on number of categories
                num_slices = len(pie_data)
                shades = color_palette[:num_slices]  # Select only required shades

                # Create the pie chart
                fig = go.Figure(go.Pie(
                    labels=pie_data['Column'],
                    values=pie_data['Sum'],
                    hole=0.3,  # Creates a donut chart; set to 0 for full pie
                    marker=dict(colors=shades),  # Apply single-shade colors
                    textinfo='label+percent',  # Show labels and percentages
                    textposition='outside',
                    insidetextfont=dict(color='Black', size=14),  # Text inside slices
                    outsidetextfont=dict(color='Black', size=14),  # Text outside slices
                    hoverinfo='label+value+percent',  # Hover info
                    pull=[0.005] * num_slices  # Slightly pull out all slices for better visibility
                ))

                # Update layout
                fig.update_layout(
                    title=dict(
                        text="📊 Contribution of Each Column to Total Sum",
                        font=dict(size=18, family="Arial", color="black")
                    ),
                    showlegend=False,
                    # legend=dict(
                    #     title="Legend",
                    #     orientation="h",  # Horizontal legend
                    #     x=0.3,
                    #     y=-0.1
                    # ),
                    margin=dict(l=40, r=40, t=80, b=40)
                )

                # Display the pie chart
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("Please select at least one column to display the pie chart.")


        import numpy as np

        with tab6:  # New Tab for Correlation Plot
            st.write("### Correlation Plot")

            # Step 1: Allow user to select columns for correlation plot
            available_columns = selected_df.select_dtypes(include='number').columns.tolist()
            default_tv_columns = [col for col in available_columns if col.startswith("TV") or col.startswith("Digital")] + ["Volume"]
            selected_columns_corr = st.multiselect(
                "Select columns for the Correlation Plot",
                available_columns,
                default=default_tv_columns,  # Default selection
                key="column_selector_corr"
            )

            with st.expander("View Selected Columns and transformations", expanded=True):

                # Step 2: Check minimum 2 columns selected
                if len(selected_columns_corr) < 2:
                    st.warning("Select at least two columns for correlation.")
                else:
                    transformed_df = selected_df.copy()

                    # Step 3: Adstock Transformation Option
                    adstock_apply = st.checkbox("Apply Adstock Transformation")

                    if adstock_apply:
                        columns_to_adstock = st.multiselect(
                            "Select columns for Adstock Transformation",
                            selected_columns_corr,
                            default=selected_columns_corr,
                            key="adstock_columns"
                        )

                        adstock_decay = st.slider(
                            "Select Adstock Decay Rate (0 to 1)",
                            min_value=0.0,
                            max_value=1.0,
                            step=0.01,
                            value=0.5,
                            key="adstock_decay"
                        )

                        for col in columns_to_adstock:
                            adstocked = []
                            prev = 0
                            for val in transformed_df[col]:
                                new_val = val + adstock_decay * prev
                                adstocked.append(new_val)
                                prev = new_val
                            transformed_df[col] = adstocked

                    # Step 4: Standardize or Min-Max Scale After Adstock
                    if adstock_apply:
                        transform_after_adstock = st.selectbox(
                            "Select Transformation After Adstock:",
                            options=["None", "Standardization (Z-score)", "Min-Max Scaling (0-1)"],
                            index=1  # Default to Standardization
                        )

                        for col in columns_to_adstock:
                            if transform_after_adstock == "Standardization (Z-score)":
                                mean_val = transformed_df[col].mean()
                                std_val = transformed_df[col].std()
                                if std_val != 0:
                                    transformed_df[col] = (transformed_df[col] - mean_val) / std_val
                                else:
                                    st.warning(f"Standard deviation is zero for {col}. Skipping standardization for {col}.")
                            
                            elif transform_after_adstock == "Min-Max Scaling (0-1)":
                                min_val = transformed_df[col].min()
                                max_val = transformed_df[col].max()
                                if max_val != min_val:
                                    transformed_df[col] = (transformed_df[col] - min_val) / (max_val - min_val)
                                else:
                                    st.warning(f"Min and Max are equal for {col}. Skipping Min-Max scaling for {col}.")



                    # Step 4: Select Transformation Type
                    transformation_option = st.selectbox(
                        "Select Additional Transformation",
                        options=["None", "Power", "Logistic", "Log-Logistic"],
                        key="transformation_selector"
                    )

                    if transformation_option != "None":
                        columns_to_transform = st.multiselect(
                            f"Select columns for {transformation_option} Transformation",
                            selected_columns_corr,
                            default=selected_columns_corr,
                            key="columns_for_transformation"
                        )

                        if transformation_option == "Power":
                            power_value = st.number_input(
                                "Enter the power value",
                                min_value=0.1,
                                max_value=10.0,
                                step=0.1,
                                value=2.0,
                                key="power_value"
                            )
                            for col in columns_to_transform:
                                transformed_df[col] = transformed_df[col] ** power_value

                        elif transformation_option == "Logistic":
                            midpoint = st.number_input(
                                "Enter the midpoint value",
                                min_value=0.0,
                                step=0.1,
                                value=1.0,
                                key="midpoint_logistic"
                            )
                            growth_rate = st.number_input(
                                "Enter the growth rate",
                                min_value=0.01,
                                step=0.01,
                                value=1.0,
                                key="growth_logistic"
                            )
                            for col in columns_to_transform:
                                transformed_df[col] = 1 / (1 + np.exp(-growth_rate * (transformed_df[col] - midpoint)))

                        elif transformation_option == "Log-Logistic":
                            midpoint = st.number_input(
                                "Enter the midpoint value (Log-Logistic)",
                                min_value=0.0,
                                step=0.1,
                                value=1.0,
                                key="midpoint_loglogistic"
                            )
                            growth_rate = st.number_input(
                                "Enter the growth rate (Log-Logistic)",
                                min_value=0.01,
                                step=0.01,
                                value=1.0,
                                key="growth_loglogistic"
                            )
                            for col in columns_to_transform:
                                transformed_df[col] = 1 / (1 + (transformed_df[col] / midpoint) ** (-growth_rate))

            # Step 5: Compute correlation matrix on final transformed data
            corr_matrix = transformed_df[selected_columns_corr].corr()

            # Step 6: Plotting the Correlation Matrix
            fig = px.imshow(
                corr_matrix,
                labels=dict(x="Variables", y="Variables", color="Correlation"),
                x=corr_matrix.columns,
                y=corr_matrix.index,
                color_continuous_scale="Purples",
                text_auto=".2f"
            )

            fig.update_layout(
                width=1000,
                height=1000,
                font=dict(size=20)
            )

            st.plotly_chart(fig, use_container_width=True)

                #     # Step 7: Plot Transformed vs Original Variables (Sorted)
                # st.write("### Transformed vs Original Variable Line Chart (Sorted)")

                # # Let user select which variable to view
                # variable_to_plot = st.selectbox(
                #     "Select a variable to compare original vs transformed (sorted)",
                #     selected_columns_corr,
                #     key="compare_transformed_sorted"
                # )

                # import plotly.graph_objects as go

                # if variable_to_plot:
                #     # Sort both original and transformed values separately
                #     original_sorted = selected_df[variable_to_plot].sort_values().reset_index(drop=True)
                #     transformed_sorted = transformed_df[variable_to_plot].sort_values().reset_index(drop=True)

                #     fig_compare_sorted = go.Figure()

                #     # Add original values (Left Y-Axis)
                #     fig_compare_sorted.add_trace(
                #         go.Scatter(
                #             x=np.arange(len(original_sorted)),
                #             y=original_sorted,
                #             mode='lines',
                #             name='Original (Sorted)',
                #             line=dict(color='blue'),
                #             yaxis='y1'  # map to left y-axis
                #         )
                #     )

                #     # Add transformed values (Right Y-Axis)
                #     fig_compare_sorted.add_trace(
                #         go.Scatter(
                #             x=np.arange(len(transformed_sorted)),
                #             y=transformed_sorted,
                #             mode='lines',
                #             name='Transformed (Sorted)',
                #             line=dict(color='red'),
                #             yaxis='y2'  # map to right y-axis
                #         )
                #     )

                #     # Set layout for dual y-axis
                #     # fig_compare_sorted.update_layout(
                #     #     title=f"Original vs Transformed (Sorted) - {variable_to_plot}",
                #     #     xaxis=dict(title="Sorted Index"),
                #     #     yaxis=dict(
                #     #         title="Original Value",
                #     #         titlefont=dict(color="blue"),
                #     #         tickfont=dict(color="blue")
                #     #     ),
                #     #     yaxis2=dict(
                #     #         title="Transformed Value",
                #     #         titlefont=dict(color="red"),
                #     #         tickfont=dict(color="red"),
                #     #         anchor="x",
                #     #         overlaying="y",
                #     #         side="right"
                #     #     ),
                #     #     width=1000,
                #     #     height=600,
                #     #     font=dict(size=16),
                #     #     legend=dict(x=0.5, y=-0.2, orientation="h")
                #     # )
                #     fig_compare_sorted.update_layout(
                #         title=f"Original vs Transformed (Sorted) - {variable_to_plot}",
                #         xaxis=dict(title="Sorted Index"),
                #         yaxis=dict(
                #             title="Original Value",
                #             titlefont=dict(color="blue"),
                #             tickfont=dict(color="blue")
                #         ),
                #         yaxis2=dict(
                #             title="Transformed Value",
                #             titlefont=dict(color="red"),
                #             tickfont=dict(color="red"),
                #             anchor="x",
                #             overlaying="y",
                #             side="right"
                #         ),
                #         width=1000,
                #         height=600,
                #         font=dict(size=16),
                #         legend=dict(
                #             orientation="h",
                #             x=0,
                #             y=1.1,  # safe zone above the chart
                #             xanchor="left"
                #         )
                #     )


                #     st.plotly_chart(fig_compare_sorted, use_container_width=True)



########################################################## Modeling Tab ##############################################################################################
########################################################## Modeling Tab ##############################################################################################
########################################################## Modeling Tab ##############################################################################################
########################################################## Modeling Tab ##############################################################################################
########################################################## Modeling Tab ##############################################################################################
########################################################## Modeling Tab ##############################################################################################


if selected == "MODEL":
    import pandas as pd
    import numpy as np
    from sklearn.preprocessing import StandardScaler
    from sklearn.base import BaseEstimator, RegressorMixin
    from sklearn.metrics import mean_absolute_percentage_error, r2_score
    from sklearn.linear_model import Ridge, LinearRegression, Lasso, ElasticNet
    import streamlit as st
    import pandas as pd
    import numpy as np
    import matplotlib.pyplot as plt
    from sklearn.preprocessing import StandardScaler, MinMaxScaler
    import plotly.graph_objects as go
    import io
    import plotly.express as px
    # import statsmodels as sm
    from statsmodels.tools import add_constant
    # import statsmodels.api as sm
    import statsmodels.regression.linear_model as sm

    # # Restrict access
    # if "authenticated" not in st.session_state or not st.session_state.authenticated:
    #     st.error("Unauthorized access! Please log in from the main page.")
    #     st.stop()  # 🚫 Stop further execution if user is not logged in

    # st.title("Modeling")

    uploaded_file = st.sidebar.file_uploader("Upload your dataset for Modeling", type=["csv", "xlsx"])

    if uploaded_file:
        try:
            # Load the dataset
            if uploaded_file.name.endswith(".csv"):
                df = pd.read_csv(uploaded_file,sheet_name="Sheet1")
            else:
                df = pd.read_excel(uploaded_file, sheet_name="Sheet1")

        except Exception as e:
            st.error(f"Error loading file: {e}")

    # Initialize df as None at the start (optional but good practice)
    # df = None
    st.session_state.final_data_for_model = df

    if "final_data_for_model" in st.session_state:
        df = st.session_state.final_data_for_model

    # First check if df exists and is not empty
    if df is not None and not df.empty:

        # Ensure the dataset has a 'Fiscal Year' column
        if "Fiscal Year" not in df.columns:
            st.error("The uploaded dataset must contain a 'Fiscal Year' column.")
        else:
            # Step 1: Let the user select one or more Fiscal Years
            fiscal_years = df["Fiscal Year"].dropna().unique()
            selected_years = st.multiselect("Select Fiscal Year(s) for EDA", sorted(fiscal_years),default=fiscal_years)

            if selected_years:
                # Filter dataset for the selected Fiscal Years
                df = df[df["Fiscal Year"].isin(selected_years)]
                # if 'Date' not in df.columns:
                #     df["Date"] = pd.to_datetime(df["Year"].astype(str) + "-" + df["Month"], format="%Y-%B")

                # # Apply to your DataFrames
                # if 'df_filtered' in locals() or 'df_filtered' in globals():
                #     try:
                #         df_filtered = create_date_column(df_filtered.copy())
                #     except Exception as e:
                #         st.error(f"Error processing df_filtered: {str(e)}")

                # st.write(f"#### EDA for Fiscal Year(s) {', '.join(map(str, selected_years))}")
                with st.expander("View Filtered Dataset"):
                    st.dataframe(df, hide_index=True)

                # Show DataFrame Shape
                st.write(f"#### **Shape of Dataset:** `{df.shape[0]}` rows × `{df.shape[1]}` columns")

        # df = df.sort_values(by=["Date"])
        # Remove columns where all values are zero
        df = df.loc[:, (df != 0).any(axis=0)]
        # df = df[~((df['Month'].isin(['November', 'December'])) & (df['Year'] == 2019))]

        if not df.empty:
            st.session_state.df = df.copy()  # Always update with new results


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


        class GeneralizedConstraintRidgeRegression(BaseEstimator, RegressorMixin):
            def __init__(self, l2_penalty=0.1, learning_rate=0.01, iterations=5000):
                self.learning_rate = learning_rate
                self.iterations = iterations
                self.l2_penalty = l2_penalty

            def fit(self, X, Y, feature_names, constraints=None):
                """
                Fit the model with constraints on specific features.

                Parameters:
                - X: Feature matrix (numpy array)
                - Y: Target variable (numpy array)
                - feature_names: List of feature names (used for constraints)
                - constraints: Dictionary with feature constraints. Example:
                    {
                        'negative': ['scaled_Price', 'Market_X_interaction_scaled_Price'],
                        'positive': ['scaled_Stores', 'scaled_Total A&P Spend']
                    }
                """
                self.m, self.n = X.shape
                self.W = np.zeros(self.n)
                self.b = 0
                self.X = X
                self.Y = Y
                self.feature_names = feature_names
                self.constraints = constraints or {}

                # Prepare indices for constraints
                self.negative_indices = [
                    feature_names.index(var) for var in self.constraints.get('negative', []) if var in feature_names
                ]
                self.positive_indices = [
                    feature_names.index(var) for var in self.constraints.get('positive', []) if var in feature_names
                ]

                for _ in range(self.iterations):
                    self.update_weights()
                return self

            def update_weights(self):
                """Gradient Descent with Constraint Application."""
                Y_pred = self.predict(self.X)
                dW = (-(2 * (self.X.T).dot(self.Y - Y_pred)) + (2 * self.l2_penalty * self.W)) / self.m
                db = -2 * np.sum(self.Y - Y_pred) / self.m

                self.W -= self.learning_rate * dW
                self.b -= self.learning_rate * db

                # Apply constraints
                self.apply_constraints()
                return self



            def apply_constraints(self):
                """Apply constraints on weights."""

                # 1. Ensure specified weights are negative or zero
                for index in self.negative_indices:
                    self.W[index] = min(self.W[index], 0)

                # 2. Ensure specified weights are positive or zero
                for index in self.positive_indices:
                    self.W[index] = max(self.W[index], 0)

                # 3. Ensure sum of weights in 'sum_negative' groups is negative or zero
                if 'sum_negative' in self.constraints:
                    for group in self.constraints['sum_negative']:
                        if len(group) == 2:  # Handle exactly two variables (base and interaction)
                            var, interaction = group
                            if var in self.feature_names and interaction in self.feature_names:
                                var_index = self.feature_names.index(var)
                                interaction_index = self.feature_names.index(interaction)
                                total_beta = self.W[var_index] + self.W[interaction_index]
                                if total_beta > 0:  # Violation of constraint
                                    deficit = -total_beta
                                    # Adjust equally between the base variable and interaction term
                                    self.W[var_index] += deficit / 2
                                    self.W[interaction_index] += deficit / 2

                # 4. Ensure sum of weights in 'sum_positive' groups is positive or zero
                if 'sum_positive' in self.constraints:
                    for group in self.constraints['sum_positive']:
                        if len(group) == 2:  # Handle exactly two variables (base and interaction)
                            var, interaction = group
                            if var in self.feature_names and interaction in self.feature_names:
                                var_index = self.feature_names.index(var)
                                interaction_index = self.feature_names.index(interaction)
                                total_beta = self.W[var_index] + self.W[interaction_index]
                                if total_beta < 0:  # Violation of constraint
                                    deficit = -total_beta
                                    # Adjust equally between the base variable and interaction term
                                    self.W[var_index] += deficit / 2
                                    self.W[interaction_index] += deficit / 2

                # ✅ NEW: 5️⃣ Custom inequality constraints (e.g., β₁ >= β₂)
                if 'custom' in self.constraints:
                    for rule in self.constraints['custom']:
                        if isinstance(rule, dict) and rule.get('relation') == '>=':
                            var1, var2 = rule['vars']
                            if var1 in self.feature_names and var2 in self.feature_names:
                                i1 = self.feature_names.index(var1)
                                i2 = self.feature_names.index(var2)

                                # Enforce β₁ >= β₂
                                if self.W[i1] < self.W[i2]:
                                    # Move halfway to equality to avoid instability
                                    avg = (self.W[i1] + self.W[i2]) / 2
                                    self.W[i1] = avg
                                    self.W[i2] = avg



            def predict(self, X):
                """Predict the target variable."""
                return X.dot(self.W) + self.b


 
        def generate_constraints_dynamic(feature_names, media_variables, other_variables, non_scaled_variables, interaction_suffix="_interaction_"):
            """
            Dynamically generate constraints based on provided media and other variables,
            excluding competition-related variables.

            Args:
                feature_names (list): List of all feature names in the dataset.
                media_variables (list): List of media variables.
                other_variables (list): List of other variables.
                non_scaled_variables (list): List of non-scaled variable names.
                interaction_suffix (str): Suffix used to identify interaction terms.

            Returns:
                dict: Generated constraints for the regression model.
            """

            # Filter out variables containing 'Competition' or 'Competitor'
            filtered_media_variables = [media for media in media_variables if "Competition" not in media and "Competitor" not in media]
            filtered_other_variables = [var for var in other_variables if "Competition" not in var and "Competitor" not in var]

            # Standardize feature names for matching
            standardized_media_vars = [f"{media}_transformed" for media in filtered_media_variables]
            standardized_other_vars = [f"scaled_{var}" for var in filtered_other_variables]

            # Identify media and other variables
            identified_media_vars = [var for var in feature_names if var in standardized_media_vars]
            identified_other_vars = [var for var in feature_names if var in standardized_other_vars]
            identified_non_scaled_vars = [var for var in feature_names if var in non_scaled_variables]

            # Remove any Competition or Competitor variables again from identified sets (for extra safety)
            identified_media_vars = [var for var in identified_media_vars if "Competition" not in var and "Competitor" not in var]
            identified_other_vars = [var for var in identified_other_vars] #if "Competition" not in var and "Competitor" not in var
            identified_non_scaled_vars = [var for var in identified_non_scaled_vars if "Competition" not in var and "Competitor" not in var]

            # Separate Price variable (must match exactly or end with "_Price")
            price_vars = [var for var in identified_other_vars if var.startswith("scaled_RPI_") or var == "scaled_Price"] #or var.split("_")[-1] == "Price"
            # competition_media = [var for var in identified_media_vars if var == "Competitors_Reach_transformed"]
            non_price_other_vars = [var for var in identified_other_vars if var not in price_vars]

            # ✅ Explicitly pull special cases
            competition_price_var = [var for var in feature_names if var == "scaled_Competition_Price"]
            competitors_reach_var = [var for var in feature_names if var == "Competitors_Reach_transformed"]

            # Identify interaction terms
            interaction_terms = [var for var in feature_names if interaction_suffix in var] #and "Competition" not in var and "Competitor" not in var

            # Group interaction terms by base variables
            interaction_map = {}
            for interaction in interaction_terms:
                base_var = interaction.split(interaction_suffix)[1]
                # if "Competition" in base_var or "Competitor" in base_var:
                #     continue
                if base_var in interaction_map:
                    interaction_map[base_var].append(interaction)
                else:
                    interaction_map[base_var] = [interaction]

            # Generate constraints
            sum_positive_constraints = []
            for var in identified_media_vars + non_price_other_vars + competition_price_var:
                if var in interaction_map:
                    for interaction_var in interaction_map[var]:
                        sum_positive_constraints.append([var, interaction_var])

            sum_negative_constraints = []
            for price_var in price_vars + competitors_reach_var:
                if price_var in interaction_map:
                    for interaction_var in interaction_map[price_var]:
                        sum_negative_constraints.append([price_var, interaction_var])

            # ✅ Generalized constraint: first media variable >= second media variable
            custom_constraints = []

            # Ensure we have at least two media variables to compare
            if len(identified_media_vars) >= 2:
                first_media_var = identified_media_vars[0]
                second_media_var = identified_media_vars[1]
                custom_constraints.append({
                    'type': 'inequality',
                    'vars': [first_media_var, second_media_var],
                    'relation': '>=',
                    'description': f'{first_media_var} >= {second_media_var}'
                })


            # Final constraints dictionary
            constraints = {
                'negative': price_vars + competitors_reach_var,
                'positive': identified_media_vars + non_price_other_vars + competition_price_var,
                'sum_positive': sum_positive_constraints,
                'sum_negative': sum_negative_constraints,
                'custom': custom_constraints  # 👈 added here
            }

            print(constraints)
            return constraints




        # Ridge Regression
        def ridge_model(alpha=0.1):
            return Ridge(alpha=alpha)

        # Linear Regression
        def linear_model():
            return LinearRegression()

        # Lasso Regression
        def lasso_model(alpha=0.1):
            return Lasso(alpha=alpha)

        # Elastic Net
        def elastic_net_model(alpha=0.1, l1_ratio=0.5):
            return ElasticNet(alpha=alpha, l1_ratio=l1_ratio)


        def calculate_aic_bic(Y_true, Y_pred, n_features):
            """Calculates AIC and BIC."""
            residuals = Y_true - Y_pred
            rss = np.sum(residuals**2)
            n_samples = len(Y_true)
            
            # Avoid division by zero errors
            if n_samples == 0 or rss == 0:
                return np.inf, np.inf  # Return large numbers to indicate error

            # AIC and BIC formulae
            aic = n_samples * np.log(rss / n_samples) + 2 * n_features
            bic = n_samples * np.log(rss / n_samples) + np.log(n_samples) * n_features

            return aic, bic





       
        ################################################################## power transformation ########################################################

        def apply_transformations_by_market(df, media_variables, other_variables, non_scaled_variables, current_transformations, standardization_method, transformation_type, powers):
            """
            Applies adstock, logistic transformations, power transformations, and standardization to the given DataFrame
            for each region separately, then appends the transformed data.

            Parameters:
            - df: The DataFrame containing the data.
            - media_variables: List of media variable names to transform.
            - other_variables: List of other variable names to standardize.
            - non_scaled_variables: List of variables to keep without scaling.
            - current_transformations: List of transformation parameters.
                For logistic: (growth_rate, carryover, midpoint)
                For power: (carryover, power)
            - standardization_method: The method for standardization ('minmax', 'zscore', or 'none').
            - transformation_type: The type of media transformation to apply ('logistic', 'power').
            - powers: List of power values for power transformation (one per media variable).
                    If None or empty, will use 1.0 as default power.
            """
            from sklearn.preprocessing import MinMaxScaler, StandardScaler
            import numpy as np
            import pandas as pd

            transformed_data_list = []  # To store transformed data for each region
            unique_regions = df["Region"].unique()  # Get unique regions

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

            for region in unique_regions:
                # Filter data for the current region
                region_df = df[df["Region"] == region].copy()

                # Standardize other variables
                for var in other_variables:
                    if scaler_class:
                        scaler = scaler_class(**scaler_params)
                        region_df[f"scaled_{var}"] = scaler.fit_transform(region_df[[var]])
                    else:
                        region_df[f"scaled_{var}"] = region_df[var]  # No scaling

                # Transform media variables
                for media_idx, media_var in enumerate(media_variables):
                    if transformation_type == 'logistic':
                        if len(current_transformations[media_idx]) != 3:
                            raise ValueError(f"Logistic transformation requires 3 parameters: growth_rate, carryover, and midpoint. Got: {current_transformations[media_idx]}")
                        gr, co, mp = current_transformations[media_idx]

                         # Check if the media variable should have midpoint zero
                        if not any(x in media_var for x in ['TV', 'Digital', 'AllMedia', 'Reach']):
                            mp = 0  # Fix midpoint to zero
                        
                        # Apply adstock using carryover
                        adstocked = adstock_function(region_df[media_var], co)
                        region_df[f"{media_var}_adstocked"] = adstocked
                        standardized = (adstocked - np.mean(adstocked)) / np.std(adstocked)
                        # standardized = (adstocked - np.min(adstocked)) / (np.max(adstocked) - np.min(adstocked))
                        region_df[f"{media_var}_logistic"] = logistic_function(standardized, gr, mp)

                        region_df[f"{media_var}_logistic"] = np.nan_to_num(region_df[f"{media_var}_logistic"])

                        if scaler_class:
                            scaler = scaler_class(**scaler_params)
                            region_df[f"{media_var}_transformed"] = scaler.fit_transform(
                                region_df[[f"{media_var}_logistic"]]
                            )
                            
                    elif transformation_type == 'power':
                        # For power transformation, current_transformations should contain (carryover, power)
                        if len(current_transformations[media_idx]) != 2:
                            raise ValueError(f"Power transformation requires 2 parameters: carryover and power. Got: {current_transformations[media_idx]}")
                        
                        co, pw = current_transformations[media_idx]
                        
                        # Apply adstock using carryover
                        adstocked = adstock_function(region_df[media_var], co)
                        region_df[f"{media_var}_adstocked"] = adstocked
                        standardized = (adstocked - np.mean(adstocked)) / np.std(adstocked)
                        # standardized = (adstocked - np.min(adstocked)) / (np.max(adstocked) - np.min(adstocked))
                        region_df[f"{media_var}_power"] = np.power(standardized, pw)
                    
                        region_df[f"{media_var}_power"] = np.nan_to_num(region_df[f"{media_var}_power"])

                        if scaler_class:
                            scaler = scaler_class(**scaler_params)
                            region_df[f"{media_var}_transformed"] = scaler.fit_transform(
                                region_df[[f"{media_var}_power"]]
                            )

                # Keep non-scaled variables as is
                for var in non_scaled_variables:
                    region_df[f"non_scaled_{var}"] = region_df[var]

                # Append the transformed region data to the list
                transformed_data_list.append(region_df)
            
            # Concatenate all transformed data
            transformed_df = pd.concat(transformed_data_list, axis=0).reset_index(drop=True)
            return transformed_df



        def calculate_region_specific_predictions_and_mape(
            stacked_model, X, Y_actual, feature_names, regions, media_variables, other_variables, non_scaled_variables
        ):
            """
            Calculate region-wise predictions and MAPE for stacked models.
            
            Parameters:
            - stacked_model: Fitted stacked regression model.
            - X: DataFrame containing independent variables (features).
            - Y_actual: Array or Series of actual dependent variable values.
            - feature_names: List of feature names from the model.
            - regions: List of unique regions.
            - media_variables: List of media variables used in the model.
            - other_variables: List of other variables used in the model.
            
            Returns:
            - region_mapes: Dictionary containing MAPE for each region.
            - region_predictions: DataFrame of predictions for each region.
            """
            region_mapes = {}
            region_predictions = {}

            for region in regions:
                # Ensure the region dummy column exists
                region_column = f"Region_{region}"
                if region_column not in X.columns:
                    raise ValueError(f"Expected region dummy column '{region_column}' not found in X.")

                # Filter the data for the specific region
                X_region = X[X[region_column] == 1]
                Y_region_actual = Y_actual[X_region.index]

                # Extract the intercept for the region
                base_intercept = stacked_model.intercept_ if hasattr(stacked_model, 'intercept_') else stacked_model.b
                region_intercept = 0  # Initialize to 0 by default

                # Check if the region-specific coefficient exists and add it
                if f"Region_{region}" in feature_names:
                    region_index = feature_names.index(f"Region_{region}")
                    region_intercept = stacked_model.coef_[region_index] if hasattr(stacked_model, 'coef_') else stacked_model.W[region_index]

                # Calculate the total intercept for the region
                intercept = base_intercept + region_intercept

                # Initialize adjusted weights for the region
                adjusted_weights = {}
                for var in [f"scaled_{var}" for var in other_variables] + [f"{media_var}_transformed" for media_var in media_variables]+ [f"non_scaled_{var}" for var in non_scaled_variables]:
                    base_beta = 0  # Default to 0 if not found
                    interaction_beta = 0  # Default to 0 if no interaction term

                    # Check for base coefficient
                    if var in feature_names:
                        var_index = feature_names.index(var)
                        base_beta = stacked_model.coef_[var_index] if hasattr(stacked_model, 'coef_') else stacked_model.W[var_index]

                    # Check for interaction term
                    interaction_term = f"{region}_interaction_{var}"
                    if interaction_term in feature_names:
                        interaction_index = feature_names.index(interaction_term)
                        interaction_beta = (
                            stacked_model.coef_[interaction_index] if hasattr(stacked_model, 'coef_') else stacked_model.W[interaction_index]
                        )

                    # Calculate the adjusted weight
                    adjusted_weights[var] = base_beta + interaction_beta

                # # Debug output
                # print("Intercept:", intercept)
                # print("Adjusted Weights:", adjusted_weights)

                # print(intercept,adjusted_weights)        

                # Extract relevant columns and calculate predictions
                relevant_columns = list(adjusted_weights.keys())
                X_filtered = X_region[relevant_columns]
                adjusted_weights_array = np.array([adjusted_weights[col] for col in relevant_columns])
                Y_region_predicted = intercept + np.dot(X_filtered, adjusted_weights_array)

                # Calculate MAPE for the region
                mape = mean_absolute_percentage_error(Y_region_actual, Y_region_predicted)
                region_mapes[region] = mape
                region_predictions[region] = Y_region_predicted

            return region_mapes, region_predictions



        # def recursive_modeling(
        #     df, Region, Market, Brand, y_variable, media_variables, other_variables,non_scaled_variables,
        #     growth_rates, carryover_rates, midpoints,
        #     model_type, standardization_method,
        #     current_media_idx=0, current_transformations=None, results=None, model_counter=1
        # ):
        #     if current_transformations is None:
        #         current_transformations = []
        #     if results is None:
        #         results = []

        #     # Base case: if all media variables have been processed
        #     if current_media_idx == len(media_variables):
        #         is_stacked = len(Region) > 1  # Determine if it's a stacked model
        #         model_type_label = f"Stacked_{model_type}" if is_stacked else model_type

        #         if is_stacked:
        #             df_filtered = df[(df["Region"].isin(Region)) & (df["Market"].isin(Market)) & (df["Brand"] == Brand)].copy()
        #         else:
        #             df_filtered = df[(df["Region"] == Region[0]) & (df["Market"].isin(Market)) & (df["Brand"] == Brand)].copy()

        #         if len(Region) == 2:
        #             # Simplify logic for two regions
        #             df_filtered = pd.concat([group for _, group in df_filtered.groupby("Region")], ignore_index=True)
        #         else:
        #             # Default logic for other cases
        #             df_filtered = df_filtered.groupby("Region").apply(lambda x: x).reset_index(drop=True)

        #         if df_filtered.empty:
        #             print(f"No data found for: {Region}, {Market}, {Brand}.")
        #             return results

        #         df_transformed = apply_transformations_by_market(
        #             df_filtered, media_variables, other_variables,non_scaled_variables, current_transformations, standardization_method
        #         )

        #         # Group by 'Region' and calculate the mean for the specified columns
        #         columns_to_average = [f"scaled_{var}" for var in other_variables] + [f"{var}_transformed" for var in media_variables] + [f"non_scaled_{var}" for var in non_scaled_variables]
        #         # print("Variables :", columns_to_average)
        #         df_transformed_Region_means = df_transformed.groupby('Region')[columns_to_average].mean()
        #         # print("df_trasformed_Region_Mean :",df_transformed_Region_means)

        #         # Create comma-separated mean strings for each variable
        #         variable_means_dict = {
        #             f"{col}_mean": ', '.join([f"{region}:{round(df_transformed_Region_means.loc[region, col], 4)}"
        #                                                     for region in df_transformed_Region_means.index])
        #             for col in columns_to_average
        #         }

        #         # print("variable_means_dict :",variable_means_dict)

        #         x_columns = [f"scaled_{var}" for var in other_variables] + [f"{var}_transformed" for var in media_variables] + [f"non_scaled_{var}" for var in non_scaled_variables]
        #         unique_regions = df_transformed["Region"].unique()

        #         if is_stacked:
        #             for region in unique_regions:
        #                 df_transformed[f"Region_{region}"] = (df_transformed["Region"] == region).astype(int)
        #                 for var in x_columns:
        #                     if not var.startswith("Region_"):
        #                         df_transformed[f"{region}_interaction_{var}"] = df_transformed[f"Region_{region}"] * df_transformed[var]

        #             x_columns += [f"Region_{region}" for region in unique_regions]
        #             x_columns += [f"{region}_interaction_{var}" for region in unique_regions for var in x_columns if not var.startswith("Region_")]

        #         X = df_transformed[x_columns].fillna(0).reset_index(drop=True)
        #         # print(X.columns)
        #         Y = df_filtered[[y_variable]].reset_index(drop=True).loc[X.index]

        #         # vif_df = calculate_vif(X)
        #         feature_names = X.columns.tolist()
        #         X_np, Y_np = X.values, Y.values.flatten()

        #         if model_type == "Ridge":
        #             model = ridge_model(alpha=0.1)
        #             model.fit(X_np, Y_np)
        #             Y_pred = model.predict(X_np)  # Define Y_pred before using it
        #             aic, bic = calculate_aic_bic(Y_np, Y_pred, X_np.shape[1])  # Correct
        #             p_values = None  # No p-values for Ridge regression


        #             # Calculate region-specific predictions and MAPE
        #             regions = [col.split('Region_')[1] for col in feature_names if col.startswith('Region_')]
        #             region_mapes, region_predictions = calculate_region_specific_predictions_and_mape(
        #                 model, X, Y_np, feature_names, regions, media_variables, other_variables,non_scaled_variables
        #             )

        #         elif model_type == "Linear Regression":
        #             model = linear_model()
        #             model.fit(X_np, Y_np)
        #             Y_pred = model.predict(X_np)  # Define Y_pred before using it

        #             # To get p-values for Linear Regression, use statsmodels OLS
        #             X_sm = add_constant(X_np)  # Add constant for intercept
        #             model_ols = sm.OLS(Y_np, X_sm)
        #             results_ols = model_ols.fit()
        #             p_values = results_ols.pvalues
        #             aic = results_ols.aic  # AIC from OLS
        #             bic = results_ols.bic  # BIC from OLS

        #             # Calculate region-specific predictions and MAPE
        #             regions = [col.split('Region_')[1] for col in feature_names if col.startswith('Region_')]
        #             region_mapes, region_predictions = calculate_region_specific_predictions_and_mape(
        #                 model, X, Y_np, feature_names, regions, media_variables, other_variables,non_scaled_variables
        #             )

        #         elif model_type == "Generalized Constrained Ridge":
        #             constraints = generate_constraints_dynamic(
        #                 feature_names=feature_names,
        #                 media_variables=media_variables,
        #                 other_variables=other_variables,
        #                 non_scaled_variables=non_scaled_variables,
        #                 interaction_suffix="_interaction_"
        #             )
        #             model = GeneralizedConstraintRidgeRegression(l2_penalty=0.1, learning_rate=0.1, iterations=10000)
        #             model.fit(X_np, Y_np, feature_names, constraints)
        #             Y_pred = model.predict(X_np)  # Define Y_pred before using it
        #             aic, bic = calculate_aic_bic(Y_np, Y_pred, X_np.shape[1])  # Correct  # Calculate AIC and BIC for Generalized Constrained Ridge
        #             p_values = None  # No p-values for Generalized Constrained Ridge

        #             # Calculate region-specific predictions and MAPE
        #             regions = [col.split('Region_')[1] for col in feature_names if col.startswith('Region_')]
        #             region_mapes, region_predictions = calculate_region_specific_predictions_and_mape(
        #                 model, X, Y_np, feature_names, regions, media_variables, other_variables,non_scaled_variables
        #             )

        #         else:
        #             raise ValueError(f"Unsupported model type: {model_type}")

        #         Y_pred = model.predict(X_np)
        #         mape = mean_absolute_percentage_error(Y_np, Y_pred)
        #         r2 = r2_score(Y_np, Y_pred)
        #         adjusted_r2 = 1 - ((1 - r2) * (len(Y_np) - 1) / (len(Y_np) - len(feature_names) - 1)) if len(Y_np) - len(feature_names) - 1 != 0 else float('nan')
        #         print(f"model_{model_counter}")

        #         results_dict = {
        #             'Model_num': f"model_{model_counter}",
        #             'Model_type': model_type_label,
        #             'Brand': Brand,
        #             'Market': Market,
        #             'Region': Region,
        #             'Model_selected': 0,
        #             'MAPE': round(mape, 4),
        #             "Region_MAPEs": ','.join([f"{region}:{round(mape, 4)}" for region, mape in region_mapes.items()]),
        #             'R_squared': round(r2, 4),
        #             'Adjusted_R_squared': round(adjusted_r2, 4),
        #             'AIC': round(aic, 4),
        #             'Y': y_variable,
        #             'beta0': model.intercept_ if hasattr(model, 'intercept_') else model.b,
        #             **{f'beta_{feature_names[i]}': model.coef_[i] if hasattr(model, 'coef_') else model.W[i] for i in range(len(feature_names))},
        #             **variable_means_dict,  # Add variable-specific mean strings
        #             'BIC': round(bic, 4),
        #             'Growth_rate': ','.join(map(str, [t[0] for t in current_transformations])),
        #             'Mid_point': ','.join(map(str, [t[2] for t in current_transformations])),
        #             'Carryover': ','.join(map(str, [t[1] for t in current_transformations])),
        #             "Standardization_method": standardization_method
        #         }

        #         # if p_values is not None:
        #         #     for i, feature in enumerate(feature_names):
        #         #         results_dict[f'p_value_{feature}'] = "Yes" if p_values[i + 1] <= 0.05 else "No"

        #         if p_values is not None:
        #             for i, feature in enumerate(feature_names):
        #                 results_dict[f'p_value_{feature}'] = p_values[i + 1] 

        #         # for _, row in vif_df.iterrows():
        #         #     results_dict[f'VIF_{row["Feature"]}'] = row["VIF"]

        #         results.append(results_dict)
        #         return results

        #     media_var = media_variables[current_media_idx]
        #     for gr in growth_rates:
        #         for co in carryover_rates:
        #             for mp in midpoints:
        #                 results = recursive_modeling(
        #                     df, Region, Market, Brand, y_variable, media_variables, other_variables,non_scaled_variables,
        #                     growth_rates, carryover_rates, midpoints,
        #                     model_type, standardization_method,
        #                     current_media_idx + 1, current_transformations + [(gr, co, mp)], results, model_counter
        #                 )
        #                 model_counter += 1
                        

        #     return results


        # def recursive_modeling(
        #     df, Region, Market, Brand, y_variable, media_variables, other_variables,non_scaled_variables,
        #     growth_rates, carryover_rates, midpoints,
        #     model_type, standardization_method, apply_same_params=True,
        #     current_media_idx=0, current_transformations=None, results=None, model_counter=1
        # ):
        #     if current_transformations is None:
        #         current_transformations = []
        #     if results is None:
        #         results = []

        #     # Base case: if all media variables have been processed
        #     if current_media_idx == len(media_variables):
        #         is_stacked = len(Region) > 1  # Determine if it's a stacked model
        #         model_type_label = f"Stacked_{model_type}" if is_stacked else model_type

        #         if is_stacked:
        #             df_filtered = df[(df["Region"].isin(Region)) & (df["Market"].isin(Market)) & (df["Brand"] == Brand)].copy()
        #         else:
        #             df_filtered = df[(df["Region"] == Region[0]) & (df["Market"].isin(Market)) & (df["Brand"] == Brand)].copy()

        #         if len(Region) == 2:
        #             # Simplify logic for two regions
        #             df_filtered = pd.concat([group for _, group in df_filtered.groupby("Region")], ignore_index=True)
        #         else:
        #             # Default logic for other cases
        #             df_filtered = df_filtered.groupby("Region").apply(lambda x: x).reset_index(drop=True)

        #         if df_filtered.empty:
        #             print(f"No data found for: {Region}, {Market}, {Brand}.")
        #             return results

        #         df_transformed = apply_transformations_by_market(
        #             df_filtered, media_variables, other_variables,non_scaled_variables, current_transformations, standardization_method
        #         )

        #         # Group by 'Region' and calculate the mean for the specified columns
        #         columns_to_average = [f"scaled_{var}" for var in other_variables] + [f"{var}_transformed" for var in media_variables] + [f"non_scaled_{var}" for var in non_scaled_variables]
        #         # print("Variables :", columns_to_average)
        #         df_transformed_Region_means = df_transformed.groupby('Region')[columns_to_average].mean()
        #         # print("df_trasformed_Region_Mean :",df_transformed_Region_means)

        #         # Create comma-separated mean strings for each variable
        #         variable_means_dict = {
        #             f"{col}_mean": ', '.join([f"{region}:{round(df_transformed_Region_means.loc[region, col], 4)}"
        #                                                     for region in df_transformed_Region_means.index])
        #             for col in columns_to_average
        #         }

        #         # print("variable_means_dict :",variable_means_dict)

        #         x_columns = [f"scaled_{var}" for var in other_variables] + [f"{var}_transformed" for var in media_variables] + [f"non_scaled_{var}" for var in non_scaled_variables]
        #         unique_regions = df_transformed["Region"].unique()

        #         if is_stacked:
        #             for region in unique_regions:
        #                 df_transformed[f"Region_{region}"] = (df_transformed["Region"] == region).astype(int)
        #                 for var in x_columns:
        #                     if not var.startswith("Region_"):
        #                         df_transformed[f"{region}_interaction_{var}"] = df_transformed[f"Region_{region}"] * df_transformed[var]

        #             x_columns += [f"Region_{region}" for region in unique_regions]
        #             x_columns += [f"{region}_interaction_{var}" for region in unique_regions for var in x_columns if not var.startswith("Region_")]

        #         X = df_transformed[x_columns].fillna(0).reset_index(drop=True)
        #         # print(X.columns)
        #         Y = df_filtered[[y_variable]].reset_index(drop=True).loc[X.index]

        #         # vif_df = calculate_vif(X)
        #         feature_names = X.columns.tolist()
        #         X_np, Y_np = X.values, Y.values.flatten()

        #         if model_type == "Ridge":
        #             model = ridge_model(alpha=0.1)
        #             model.fit(X_np, Y_np)
        #             Y_pred = model.predict(X_np)  # Define Y_pred before using it
        #             aic, bic = calculate_aic_bic(Y_np, Y_pred, X_np.shape[1])  # Correct
        #             p_values = None  # No p-values for Ridge regression


        #             # Calculate region-specific predictions and MAPE
        #             regions = [col.split('Region_')[1] for col in feature_names if col.startswith('Region_')]
        #             region_mapes, region_predictions = calculate_region_specific_predictions_and_mape(
        #                 model, X, Y_np, feature_names, regions, media_variables, other_variables,non_scaled_variables
        #             )

        #         elif model_type == "Lasso":
        #             model = lasso_model(alpha=0.1)
        #             model.fit(X_np, Y_np)
        #             Y_pred = model.predict(X_np)  # Define Y_pred before using it
        #             aic, bic = calculate_aic_bic(Y_np, Y_pred, X_np.shape[1])  # Correct
        #             p_values = None  # No p-values for Ridge regression


        #             # Calculate region-specific predictions and MAPE
        #             regions = [col.split('Region_')[1] for col in feature_names if col.startswith('Region_')]
        #             region_mapes, region_predictions = calculate_region_specific_predictions_and_mape(
        #                 model, X, Y_np, feature_names, regions, media_variables, other_variables,non_scaled_variables
        #             )

        #         elif model_type == "Elastic Net":
        #             model = elastic_net_model(alpha=0.1, l1_ratio=0.5)
        #             model.fit(X_np, Y_np)
        #             Y_pred = model.predict(X_np)  # Define Y_pred before using it
        #             aic, bic = calculate_aic_bic(Y_np, Y_pred, X_np.shape[1])  # Correct
        #             p_values = None  # No p-values for Ridge regression


        #             # Calculate region-specific predictions and MAPE
        #             regions = [col.split('Region_')[1] for col in feature_names if col.startswith('Region_')]
        #             region_mapes, region_predictions = calculate_region_specific_predictions_and_mape(
        #                 model, X, Y_np, feature_names, regions, media_variables, other_variables,non_scaled_variables
        #             )

        #         elif model_type == "Linear Regression":
        #             model = linear_model()
        #             model.fit(X_np, Y_np)
        #             Y_pred = model.predict(X_np)  # Define Y_pred before using it

        #             # To get p-values for Linear Regression, use statsmodels OLS
        #             X_sm = add_constant(X_np)  # Add constant for intercept
        #             model_ols = sm.OLS(Y_np, X_sm)
        #             results_ols = model_ols.fit()
        #             p_values = results_ols.pvalues
        #             aic = results_ols.aic  # AIC from OLS
        #             bic = results_ols.bic  # BIC from OLS

        #             # Calculate region-specific predictions and MAPE
        #             regions = [col.split('Region_')[1] for col in feature_names if col.startswith('Region_')]
        #             region_mapes, region_predictions = calculate_region_specific_predictions_and_mape(
        #                 model, X, Y_np, feature_names, regions, media_variables, other_variables,non_scaled_variables
        #             )

        #         elif model_type == "Generalized Constrained Ridge":
        #             constraints = generate_constraints_dynamic(
        #                 feature_names=feature_names,
        #                 media_variables=media_variables,
        #                 other_variables=other_variables,
        #                 non_scaled_variables=non_scaled_variables,
        #                 interaction_suffix="_interaction_"
        #             )
        #             model = GeneralizedConstraintRidgeRegression(l2_penalty=0.1, learning_rate=0.1, iterations=10000)
        #             model.fit(X_np, Y_np, feature_names, constraints)
        #             Y_pred = model.predict(X_np)  # Define Y_pred before using it
        #             aic, bic = calculate_aic_bic(Y_np, Y_pred, X_np.shape[1])  # Correct  # Calculate AIC and BIC for Generalized Constrained Ridge
        #             p_values = None  # No p-values for Generalized Constrained Ridge

        #             # Calculate region-specific predictions and MAPE
        #             regions = [col.split('Region_')[1] for col in feature_names if col.startswith('Region_')]
        #             region_mapes, region_predictions = calculate_region_specific_predictions_and_mape(
        #                 model, X, Y_np, feature_names, regions, media_variables, other_variables,non_scaled_variables
        #             )

        #         else:
        #             raise ValueError(f"Unsupported model type: {model_type}")

        #         Y_pred = model.predict(X_np)
        #         mape = mean_absolute_percentage_error(Y_np, Y_pred)
        #         r2 = r2_score(Y_np, Y_pred)
        #         adjusted_r2 = 1 - ((1 - r2) * (len(Y_np) - 1) / (len(Y_np) - len(feature_names) - 1)) if len(Y_np) - len(feature_names) - 1 != 0 else float('nan')
        #         print(f"model_{model_counter}")

        #         results_dict = {
        #             'Model_num': f"model_{model_counter}",
        #             'Model_type': model_type_label,
        #             'Brand': Brand,
        #             'Market': Market,
        #             'Region': Region,
        #             'Model_selected': 0,
        #             'MAPE': round(mape, 4),
        #             "Region_MAPEs": ','.join([f"{region}:{round(mape, 4)}" for region, mape in region_mapes.items()]),
        #             'R_squared': round(r2, 4),
        #             'Adjusted_R_squared': round(adjusted_r2, 4),
        #             'AIC': round(aic, 4),
        #             'Y': y_variable,
        #             'beta0': model.intercept_ if hasattr(model, 'intercept_') else model.b,
        #             **{f'beta_{feature_names[i]}': model.coef_[i] if hasattr(model, 'coef_') else model.W[i] for i in range(len(feature_names))},
        #             **variable_means_dict,  # Add variable-specific mean strings
        #             'BIC': round(bic, 4),
        #             'Growth_rate': ','.join(map(str, [t[0] for t in current_transformations])),
        #             'Mid_point': ','.join(map(str, [t[2] for t in current_transformations])),
        #             'Carryover': ','.join(map(str, [t[1] for t in current_transformations])),
        #             "Standardization_method": standardization_method
        #         }

        #         # if p_values is not None:
        #         #     for i, feature in enumerate(feature_names):
        #         #         results_dict[f'p_value_{feature}'] = "Yes" if p_values[i + 1] <= 0.05 else "No"

        #         if p_values is not None:
        #             for i, feature in enumerate(feature_names):
        #                 results_dict[f'p_value_{feature}'] = p_values[i + 1] 

        #         # for _, row in vif_df.iterrows():
        #         #     results_dict[f'VIF_{row["Feature"]}'] = row["VIF"]

        #         results.append(results_dict)
        #         return results

        #     # media_var = media_variables[current_media_idx]
        #     # for gr in growth_rates:
        #     #     for co in carryover_rates:
        #     #         for mp in midpoints:
        #     #             results = recursive_modeling(
        #     #                 df, Region, Market, Brand, y_variable, media_variables, other_variables,non_scaled_variables,
        #     #                 growth_rates, carryover_rates, midpoints,
        #     #                 model_type, standardization_method,
        #     #                 current_media_idx + 1, current_transformations + [(gr, co, mp)], results, model_counter
        #     #             )
        #     #             model_counter += 1

        #     # Single set of transformations for all media variables
        #     # for gr in growth_rates:
        #     #     for co in carryover_rates:
        #     #         for mp in midpoints:
        #     #             transformations = [(gr, co, mp)] * len(media_variables)
        #     #             results = recursive_modeling(
        #     #                 df, Region, Market, Brand, y_variable, media_variables, other_variables, non_scaled_variables,
        #     #                 growth_rates, carryover_rates, midpoints,
        #     #                 model_type, standardization_method, 
        #     #                 len(media_variables), transformations, results, model_counter
        #     #             )
        #     #             model_counter += 1
                        

        #     # return results
        #     # Recursive case
        #     media_var = media_variables[current_media_idx]
            
            # if apply_same_params == "Yes":
            #     # Apply one transformation to all media variables
            #     for gr in growth_rates:
            #         for co in carryover_rates:
            #             for mp in midpoints:
            #                 # Apply the same (gr, co, mp) to all media variables
            #                 transformations = [(gr, co, mp)] * len(media_variables)
            #                 results = recursive_modeling(
            #                     df, Region, Market, Brand, y_variable, media_variables, other_variables, non_scaled_variables,
            #                     growth_rates, carryover_rates, midpoints,
            #                     model_type, standardization_method, apply_same_params,
            #                     len(media_variables), transformations, results, model_counter
            #                 )
            #                 model_counter += 1
            # else:
            #     # Iterate transformations separately for each media variable
            #     for gr in growth_rates:
            #         for co in carryover_rates:
            #             for mp in midpoints:
            #                 results = recursive_modeling(
            #                     df, Region, Market, Brand, y_variable, media_variables, other_variables, non_scaled_variables,
            #                     growth_rates, carryover_rates, midpoints,
            #                     model_type, standardization_method, apply_same_params,
            #                     current_media_idx + 1, current_transformations + [(gr, co, mp)], results, model_counter
            #                 )
            #                 model_counter += 1

            # return results


        # def generalized_modeling_recursive(
        #     df, Region, Market, Brand, y_variables, media_variables, other_variables,non_scaled_variables,
        #     growth_rates, carryover_rates, midpoints, model_types, standardization_method, apply_same_params
        # ):
        #     """
        #     Generalized function to run models for multiple brands step-by-step.
        #     Includes both stacked models and individual models for each region.
            
        #     Parameters:
        #     - df: DataFrame containing the data.
        #     - Region: List of regions to include.
        #     - Market: List of markets to include.
        #     - Brand: List of brands to include.
        #     - y_variables: List of dependent variables to model.
        #     - media_variables: List of media variables to transform and model.
        #     - other_variables: List of other variables to standardize and model.
        #     - growth_rates: List of growth rates for transformations.
        #     - carryover_rates: List of carryover rates for transformations.
        #     - midpoints: List of midpoints for logistic transformations.
        #     - model_types: List of model types to fit (e.g., Ridge, Linear Regression).
        #     - standardization_method: Standardization method to use ('minmax', 'zscore', or 'none').
            
        #     Returns:
        #     - A DataFrame containing results for all models (stacked and region-specific).
        #     """
        #     results = []  # To store results for all models
        #     model_counter = 1

        #     for brand in Brand:
        #         print(f"Processing brand: {brand}")

        #         for model_type in model_types:  # Iterate over specified models
        #             print(f"  Running {model_type} models...")

        #             for y_variable in y_variables:
        #                 print(f"    Modeling for dependent variable: {y_variable}")

        #                 # Stacked Model (all regions together with dummies and interactions)
        #                 results = recursive_modeling(
        #                     df, Region, Market, brand, y_variable, media_variables, other_variables,non_scaled_variables,
        #                     growth_rates, carryover_rates, midpoints,
        #                     model_type, standardization_method, apply_same_params=apply_same_params,
        #                     current_media_idx=0, current_transformations=[], results=results, model_counter=model_counter
        #                 )
        #                 model_counter += 1

        #                 # Region-Specific Models (one per region)
        #                 for region in Region:
        #                     print(f"    Running region-specific model for Region: {region}")
                            
        #                     results = recursive_modeling(
        #                         df, [region], Market, brand, y_variable, media_variables, other_variables,non_scaled_variables,
        #                         growth_rates, carryover_rates, midpoints,
        #                         model_type, standardization_method,apply_same_params=apply_same_params,
        #                         current_media_idx=0, current_transformations=[], results=results, model_counter=model_counter
        #                     )
        #                     model_counter += 1
                            
        #     # Combine all results into a single DataFrame
        #     return pd.DataFrame(results)

        ############################################################################################ power transformation ####################################################################


        # def recursive_modeling(
        #     df, Region, Market, Brand, y_variable, media_variables, other_variables, non_scaled_variables,
        #     growth_rates, carryover_rates, midpoints, powers,  # Transformation parameters
        #     model_type, standardization_method, transformation_type, apply_same_params=True,
        #     current_media_idx=0, current_transformations=None, results=None, model_counter=1
        # ):
        # def recursive_modeling(
        #     df, Region, Market, Brand, y_variable, media_variables, other_variables, non_scaled_variables,
        #     growth_rates, carryover_rates, midpoints, powers,
        #     model_type, standardization_method, transformation_type, apply_same_params=True,
        #     current_media_idx=0, current_transformations=None, results=None, model_counter=1,
        #     same_carryover=False, fixed_carryover=None
        # ):
        def recursive_modeling(
            df, Region, Market, Brand, y_variable, media_variables, other_variables, non_scaled_variables,
            growth_rates, carryover_rates, midpoints, powers,
            model_type, standardization_method, transformation_type, apply_same_params=True,
            current_media_idx=0, current_transformations=None, results=None, model_counter=1,
            same_carryover=False, fixed_carryover=None,
            own_media_variables=['TV_Reach', 'Digital_Reach', 'AllMedia_Reach'],  # Pass your own brand media
            fixed_midpoint=0  # Fixed midpoint for competitor media
        ):
            if current_transformations is None:
                current_transformations = []
            if results is None:
                results = []

            # st.write(current_transformations)

            # Base case: if all media variables have been processed
            if current_media_idx == len(media_variables):
                is_stacked = len(Region) > 1  # Determine if it's a stacked model
                model_type_label = f"Stacked_{model_type}" if is_stacked else model_type

                if is_stacked:
                    df_filtered = df[(df["Region"].isin(Region)) & (df["Market"].isin(Market)) & (df["Brand"] == Brand)].copy()
                else:
                    df_filtered = df[(df["Region"] == Region[0]) & (df["Market"].isin(Market)) & (df["Brand"] == Brand)].copy()

                if len(Region) == 2:
                    df_filtered = pd.concat([group for _, group in df_filtered.groupby("Region")], ignore_index=True)
                else:
                    df_filtered = df_filtered.groupby("Region").apply(lambda x: x).reset_index(drop=True)

                if df_filtered.empty:
                    print(f"No data found for: {Region}, {Market}, {Brand}.")
                    return results
                

                X_col = [f"{var}" for var in other_variables] + [f"{var}" for var in media_variables] + [f"{var}" for var in non_scaled_variables] 
                # st.write("X_col :", X_col)
                # st.write(df_filtered[X_col].isna().sum())
                df_filtered = df_filtered.dropna(subset=X_col)
                # st.write(df_filtered[X_col].isna().sum())
                # df_filtered = df_filtered.dropna(subset=[f"{var}" for var in other_variables], how='all')
                # st.write(df_filtered.isna().sum())

                df_transformed = apply_transformations_by_market(
                    df_filtered, media_variables, other_variables, non_scaled_variables, 
                    current_transformations, standardization_method, transformation_type, powers
                )
                # st.write(df_transformed.mean())
                # st.dataframe(df_transformed)

                columns_to_average_scaled = [f"scaled_{var}" for var in other_variables] + [f"{var}_transformed" for var in media_variables] + [f"non_scaled_{var}" for var in non_scaled_variables] 
                df_transformed_Region_means = df_transformed.groupby('Region')[columns_to_average_scaled].mean()
                # print("Variables :", columns_to_average)
                # df_transformed_Region_means = df_transformed.groupby('Region')[columns_to_average].mean()
                # st.write("df_trasformed_Region_Mean :",df_transformed_Region_means)

                scaled_variable_means_dict = {
                    f"{col}_mean": ', '.join([f"{region}:{round(df_transformed_Region_means.loc[region, col], 4)}"
                                                for region in df_transformed_Region_means.index])
                    for col in columns_to_average_scaled
                }

                columns_to_average = [f"{var}" for var in other_variables] + [f"{var}" for var in media_variables] + [f"{var}" for var in non_scaled_variables]
                df_filtered_Region_means = df_filtered.groupby('Region')[columns_to_average].mean()
                df_filtered_Region_std = df_filtered.groupby('Region')[columns_to_average].std()
                # print("Variables :", columns_to_average)
                # df_transformed_Region_means = df_transformed.groupby('Region')[columns_to_average].mean()
                # st.write("df_trasformed_Region_Mean :",df_transformed_Region_means)

                variable_means_dict = {
                    f"{col}_mean": ', '.join([f"{region}:{round(df_filtered_Region_means.loc[region, col], 4)}"
                                                for region in df_filtered_Region_means.index])
                    for col in columns_to_average
                }
                variable_std_dict = {
                    f"{col}_std": ', '.join([f"{region}:{round(df_filtered_Region_std.loc[region, col], 4)}"
                                                for region in df_filtered_Region_std.index])
                    for col in columns_to_average
                }
                # st.write(variable_means_dict)

                ### storing 1/(max-min) for scaled var

                columns_to_minmax = [f"{var}" for var in other_variables]
                # st.write(columns_to_minmax)
                df_filtered_Region_max = df_filtered.groupby('Region')[columns_to_minmax].max()
                df_filtered_Region_min = df_filtered.groupby('Region')[columns_to_minmax].min()
                # st.write(df_filtered_Region_max)
                # st.write(df_filtered_Region_min)

                variable_scale_factor_dict = {
                    f"{col}_range": ', '.join([
                        f"{region}:{round(1 / (df_filtered_Region_max.loc[region, col] - df_filtered_Region_min.loc[region, col]), 6)}"
                        if (df_filtered_Region_max.loc[region, col] - df_filtered_Region_min.loc[region, col]) != 0 else f"{region}:inf"
                        for region in df_filtered_Region_max.index
                    ])
                    for col in columns_to_minmax
                }
                # st.write(variable_scale_factor_dict)

                logistic_sensitivity_dict = {}

                for var in media_variables:
                    adstock_col = f"{var}_adstocked"
                    trans_col = f"{var}_logistic"  # this is the logistic output

                    region_values = []

                    for region in df_filtered['Region'].unique():
                        df_region = df_transformed[df_transformed['Region'] == region]

                        if adstock_col not in df_region.columns or trans_col not in df_region.columns:
                            region_values.append(f"{region}:NA")
                            continue

                        logistic_mean = df_region[trans_col].mean()
                        adstock_mean = df_region[adstock_col].mean()
                        adstock_std = df_region[adstock_col].std()
                        media_mean = df_region[var].mean()
                        logistic_max = df_region[trans_col].max()
                        logistic_min = df_region[trans_col].min()

                        if pd.isna(logistic_mean) or pd.isna(adstock_mean) or pd.isna(adstock_std) or adstock_std == 0:
                            region_values.append(f"{region}:NA")
                            continue

                        # Compute sensitivity value
                        sensitivity_value = (1/(logistic_max - logistic_min)) * (logistic_mean * (1 - logistic_mean)) * (media_mean) * (1/ adstock_std)
                        region_values.append(f"{region}:{round(sensitivity_value, 6)}")

                    logistic_sensitivity_dict[f"{var}_sensitivity"] = ', '.join(region_values)



                # st.write("empirical_slopes :", empirical_slopes_dict)
                # st.write("variable_means_dict :",variable_means_dict)

                x_columns = [f"scaled_{var}" for var in other_variables] + [f"{var}_transformed" for var in media_variables] + [f"non_scaled_{var}" for var in non_scaled_variables]
                unique_regions = df_transformed["Region"].unique()

              
                if is_stacked:
                    for region in unique_regions:
                        df_transformed[f"Region_{region}"] = (df_transformed["Region"] == region).astype(int)
                        for var in x_columns:
                            if not var.startswith("Region_"):
                                df_transformed[f"{region}_interaction_{var}"] = df_transformed[f"Region_{region}"] * df_transformed[var]

                    x_columns += [f"Region_{region}" for region in unique_regions]
                    x_columns += [f"{region}_interaction_{var}" for region in unique_regions for var in x_columns if not var.startswith("Region_")]

                X = df_transformed[x_columns].reset_index(drop=True)
                # st.write(X.mean())
                Y = df_filtered[[y_variable]].reset_index(drop=True)

                # region_to_indices = {
                #         region: df_filtered[df_filtered["Region"] == region].index.tolist()
                #         for region in df_filtered["Region"].unique()
                #     }
            

                feature_names = X.columns.tolist()
                # # Combine X and Y into a single DataFrame
                # XY = pd.concat([X, Y], axis=1)
                # st.write("XY nan values count:",XY.isna().sum().sum())

                # # Drop rows with NaNs and reset index
                # XY_clean = XY.dropna().reset_index(drop=True)
                # # st.write("XY_clean nan values count:",XY_clean.isna().sum().sum())

                # # Split back into X and Y
                # X_np = XY_clean[X.columns].values
                # Y_np = XY_clean[Y.columns[0]].values.flatten()
                # Keep Region in merged frame for region-wise stats
                XY = pd.concat([X, Y, df_filtered[["Region"]].reset_index(drop=True)], axis=1)

                # Drop rows with NaNs
                XY_clean = XY.dropna().reset_index(drop=True)

                # Extract final X, Y
                X_np = XY_clean[X.columns].values
                Y_np = XY_clean[Y.columns[0]].values.flatten()

                # Correct region index mapping (based on cleaned data!)
                region_to_indices = {
                    region: XY_clean[XY_clean["Region"] == region].index.tolist()
                    for region in XY_clean["Region"].unique()
                }

                # Safe to compute
                region_y_means = {
                    region: float(np.mean(Y_np[indices]))
                    for region, indices in region_to_indices.items()
                }

                

                # st.write("XY_clean shape:", XY_clean.shape)
                # st.write("X_np shape:", X_np.shape)
                # st.write("Y_np shape:", Y_np.shape)

                # X_np, Y_np = X.values, Y.values.flatten()
                # Assuming X and Y are pandas DataFrames or Series
                # model_df = pd.concat([X, Y], axis=1).dropna()

                # X_np, Y_np = model_df.iloc[:, :-1].values, model_df.iloc[:, -1].values


                # region_y_means = {
                #         region: float(np.mean(Y_np[indices]))
                #         for region, indices in region_to_indices.items()
                #     }

                if model_type == "Ridge":
                    model = ridge_model(alpha=0.8)
                    model.fit(X_np, Y_np)
                    Y_pred = model.predict(X_np)  # Define Y_pred before using it
                    aic, bic = calculate_aic_bic(Y_np, Y_pred, X_np.shape[1])  # Correct
                    p_values = None  # No p-values for Ridge regression


                    # Calculate region-specific predictions and MAPE
                    regions = [col.split('Region_')[1] for col in feature_names if col.startswith('Region_')]
                    region_mapes, region_predictions = calculate_region_specific_predictions_and_mape(
                        model, X, Y_np, feature_names, regions, media_variables, other_variables,non_scaled_variables
                    )

                elif model_type == "Lasso":
                    model = lasso_model(alpha=0.1)
                    model.fit(X_np, Y_np)
                    Y_pred = model.predict(X_np)  # Define Y_pred before using it
                    aic, bic = calculate_aic_bic(Y_np, Y_pred, X_np.shape[1])  # Correct
                    p_values = None  # No p-values for Ridge regression


                    # Calculate region-specific predictions and MAPE
                    regions = [col.split('Region_')[1] for col in feature_names if col.startswith('Region_')]
                    region_mapes, region_predictions = calculate_region_specific_predictions_and_mape(
                        model, X, Y_np, feature_names, regions, media_variables, other_variables,non_scaled_variables
                    )

                elif model_type == "Elastic Net":
                    model = elastic_net_model(alpha=0.1, l1_ratio=0.5)
                    model.fit(X_np, Y_np)
                    Y_pred = model.predict(X_np)  # Define Y_pred before using it
                    aic, bic = calculate_aic_bic(Y_np, Y_pred, X_np.shape[1])  # Correct
                    p_values = None  # No p-values for Ridge regression


                    # Calculate region-specific predictions and MAPE
                    regions = [col.split('Region_')[1] for col in feature_names if col.startswith('Region_')]
                    region_mapes, region_predictions = calculate_region_specific_predictions_and_mape(
                        model, X, Y_np, feature_names, regions, media_variables, other_variables,non_scaled_variables
                    )

                elif model_type == "Linear Regression":
                    model = linear_model()
                    model.fit(X_np, Y_np)
                    Y_pred = model.predict(X_np)  # Define Y_pred before using it

                    # To get p-values for Linear Regression, use statsmodels OLS
                    X_sm = add_constant(X_np)  # Add constant for intercept
                    model_ols = sm.OLS(Y_np, X_sm)
                    results_ols = model_ols.fit()
                    p_values = results_ols.pvalues
                    aic = results_ols.aic  # AIC from OLS
                    bic = results_ols.bic  # BIC from OLS

                    # Calculate region-specific predictions and MAPE
                    regions = [col.split('Region_')[1] for col in feature_names if col.startswith('Region_')]
                    region_mapes, region_predictions = calculate_region_specific_predictions_and_mape(
                        model, X, Y_np, feature_names, regions, media_variables, other_variables,non_scaled_variables
                    )

                elif model_type == "Generalized Constrained Ridge":
                    constraints = generate_constraints_dynamic(
                        feature_names=feature_names,
                        media_variables=media_variables,
                        other_variables=other_variables,
                        non_scaled_variables=non_scaled_variables,
                        interaction_suffix="_interaction_"
                    )
                    model = GeneralizedConstraintRidgeRegression(l2_penalty=0.1, learning_rate=1e-2, iterations=50000)
                    model.fit(X_np, Y_np, feature_names, constraints)
                    Y_pred = model.predict(X_np)  # Define Y_pred before using it
                    aic, bic = calculate_aic_bic(Y_np, Y_pred, X_np.shape[1])  # Correct  # Calculate AIC and BIC for Generalized Constrained Ridge
                    p_values = None  # No p-values for Generalized Constrained Ridge

                    # Calculate region-specific predictions and MAPE
                    regions = [col.split('Region_')[1] for col in feature_names if col.startswith('Region_')]
                    region_mapes, region_predictions = calculate_region_specific_predictions_and_mape(
                        model, X, Y_np, feature_names, regions, media_variables, other_variables,non_scaled_variables
                    )

                else:
                    raise ValueError(f"Unsupported model type: {model_type}")

                Y_pred = model.predict(X_np)
                Y_mean = np.mean(Y_np)
                mape = mean_absolute_percentage_error(Y_np, Y_pred)
                Y_mean_mape = mean_absolute_percentage_error(Y_np,np.full_like(Y_np, Y_mean))
                r2 = r2_score(Y_np, Y_pred)
                adjusted_r2 = 1 - ((1 - r2) * (len(Y_np) - 1) / (len(Y_np) - len(feature_names) - 1)) if len(Y_np) - len(feature_names) - 1 != 0 else float('nan')
                print(f"model_{model_counter}")
                

                results_dict = {
                    'Model_num': f"model_{model_counter}",
                    'Model_type': model_type_label,
                    'Brand': Brand,
                    'Market': Market,
                    'Region': Region,
                    'Model_selected': 0,
                    'MAPE': round(mape, 4),
                    'Avg_MAPE': round(Y_mean_mape,4),
                    "Region_MAPEs": ','.join([f"{region}:{round(mape, 4)}" for region, mape in region_mapes.items()]),
                    'R_squared': round(r2, 4),
                    'Adjusted_R_squared': round(adjusted_r2, 4),
                    'AIC': round(aic, 4),
                    'Y': y_variable,
                    # 'Y_mean': round(Y_mean, 4),
                    "Region_Y_means": ','.join([f"{region}:{round(mean, 4)}" for region, mean in region_y_means.items()]),
                    'beta0': model.intercept_ if hasattr(model, 'intercept_') else model.b,
                    **{f'beta_{feature_names[i]}': model.coef_[i] if hasattr(model, 'coef_') else model.W[i] for i in range(len(feature_names))},
                    **scaled_variable_means_dict,  # Add variable-specific mean strings
                    **variable_std_dict,  # Add variable-specific std strings
                    **variable_means_dict,  # Add variable-specific mean strings
                    **logistic_sensitivity_dict,  # Add empirical slopes for media variables
                    **variable_scale_factor_dict,
                    'BIC': round(bic, 4),
                    'Transformation_type': transformation_type,
                    'Transformation_params': ','.join(map(str, current_transformations)),
                    "Standardization_method": standardization_method
                }

                # if p_values is not None:
                #     for i, feature in enumerate(feature_names):
                #         results_dict[f'p_value_{feature}'] = "Yes" if p_values[i + 1] <= 0.05 else "No"

                # Add transformation parameters
                if transformation_type == "logistic":
                    results_dict.update({
                        'Growth_rate': ','.join(map(str, [t[0] for t in current_transformations])),
                        'Carryover': ','.join(map(str, [t[1] for t in current_transformations])),
                        'Mid_point': ','.join(map(str, [t[2] for t in current_transformations]))
                    })
                elif transformation_type == "power":
                    results_dict.update({
                        'Carryover': ','.join(map(str, [t[0] for t in current_transformations])),
                        'Power': ','.join(map(str, [t[1] if len(t) > 1 else 'N/A' for t in current_transformations]))
                    })



                if p_values is not None:
                    for i, feature in enumerate(feature_names):
                        results_dict[f'p_value_{feature}'] = p_values[i + 1] 

                # for _, row in vif_df.iterrows():
                #     results_dict[f'VIF_{row["Feature"]}'] = row["VIF"]

                results.append(results_dict)
                return results
            
            media_var = media_variables[current_media_idx]
            is_own_brand_media = media_var in own_media_variables

            if apply_same_params == "Yes":
                if transformation_type == "logistic":
                    if not growth_rates or not carryover_rates or not midpoints:
                        return results
                    gr = growth_rates[0]
                    co = carryover_rates[0]
                    mp = midpoints[0]
                    transformations = [(gr, co, mp)] * len(media_variables)
                    return recursive_modeling(
                        df, Region, Market, Brand, y_variable, media_variables, other_variables, non_scaled_variables,
                        growth_rates, carryover_rates, midpoints, powers,
                        model_type, standardization_method, transformation_type, apply_same_params,
                        len(media_variables), transformations, results, model_counter,
                        same_carryover, fixed_carryover, own_media_variables, fixed_midpoint
                    )

                elif transformation_type == "power":
                    if not carryover_rates or not powers:
                        return results
                    co = carryover_rates[0]
                    pw = powers[0]
                    transformations = [(co, pw)] * len(media_variables)
                    return recursive_modeling(
                        df, Region, Market, Brand, y_variable, media_variables, other_variables, non_scaled_variables,
                        growth_rates, carryover_rates, midpoints, powers,
                        model_type, standardization_method, transformation_type, apply_same_params,
                        len(media_variables), transformations, results, model_counter,
                        same_carryover, fixed_carryover, own_media_variables, fixed_midpoint
                    )

            else:
                if same_carryover == "Yes":
                    for co in carryover_rates:
                        if transformation_type == "logistic":
                            if is_own_brand_media:
                                for gr in growth_rates:
                                    for mp in midpoints:
                                        results = recursive_modeling(
                                            df, Region, Market, Brand, y_variable, media_variables, other_variables, non_scaled_variables,
                                            growth_rates, carryover_rates, midpoints, powers,
                                            model_type, standardization_method, transformation_type, apply_same_params,
                                            current_media_idx + 1, current_transformations + [(gr, co, mp)], results, model_counter,
                                            same_carryover, co, own_media_variables, fixed_midpoint
                                        )
                            else:
                                gr = growth_rates[0]  # Fixed growth rate for competitor
                                mp = fixed_midpoint   # Fixed midpoint for competitor
                                results = recursive_modeling(
                                    df, Region, Market, Brand, y_variable, media_variables, other_variables, non_scaled_variables,
                                    growth_rates, carryover_rates, midpoints, powers,
                                    model_type, standardization_method, transformation_type, apply_same_params,
                                    current_media_idx + 1, current_transformations + [(gr, co, mp)], results, model_counter,
                                    same_carryover, co, own_media_variables, fixed_midpoint
                                )

                        elif transformation_type == "power":
                            if is_own_brand_media:
                                for pw in powers:
                                    results = recursive_modeling(
                                        df, Region, Market, Brand, y_variable, media_variables, other_variables, non_scaled_variables,
                                        growth_rates, carryover_rates, midpoints, powers,
                                        model_type, standardization_method, transformation_type, apply_same_params,
                                        current_media_idx + 1, current_transformations + [(co, pw)], results, model_counter,
                                        same_carryover, co, own_media_variables, fixed_midpoint
                                    )
                            else:
                                pw = powers[0]  # Fixed power for competitor
                                results = recursive_modeling(
                                    df, Region, Market, Brand, y_variable, media_variables, other_variables, non_scaled_variables,
                                    growth_rates, carryover_rates, midpoints, powers,
                                    model_type, standardization_method, transformation_type, apply_same_params,
                                    current_media_idx + 1, current_transformations + [(co, pw)], results, model_counter,
                                    same_carryover, co, own_media_variables, fixed_midpoint
                                )

                else:  # same_carryover == "No"
                    if transformation_type == "logistic":
                        if is_own_brand_media:
                            for gr in growth_rates:
                                for co in carryover_rates:
                                    for mp in midpoints:
                                        results = recursive_modeling(
                                            df, Region, Market, Brand, y_variable, media_variables, other_variables, non_scaled_variables,
                                            growth_rates, carryover_rates, midpoints, powers,
                                            model_type, standardization_method, transformation_type, apply_same_params,
                                            current_media_idx + 1, current_transformations + [(gr, co, mp)], results, model_counter,
                                            same_carryover, None, own_media_variables, fixed_midpoint
                                        )
                        else:
                            gr = growth_rates[0]
                            co = carryover_rates[0]
                            mp = fixed_midpoint  # Fixed midpoint for competitor
                            results = recursive_modeling(
                                df, Region, Market, Brand, y_variable, media_variables, other_variables, non_scaled_variables,
                                growth_rates, carryover_rates, midpoints, powers,
                                model_type, standardization_method, transformation_type, apply_same_params,
                                current_media_idx + 1, current_transformations + [(gr, co, mp)], results, model_counter,
                                same_carryover, None, own_media_variables, fixed_midpoint
                            )

                    elif transformation_type == "power":
                        if is_own_brand_media:
                            for co in carryover_rates:
                                for pw in powers:
                                    results = recursive_modeling(
                                        df, Region, Market, Brand, y_variable, media_variables, other_variables, non_scaled_variables,
                                        growth_rates, carryover_rates, midpoints, powers,
                                        model_type, standardization_method, transformation_type, apply_same_params,
                                        current_media_idx + 1, current_transformations + [(co, pw)], results, model_counter,
                                        same_carryover, None, own_media_variables, fixed_midpoint
                                    )
                        else:
                            co = carryover_rates[0]
                            pw = powers[0]  # Fixed power for competitor
                            results = recursive_modeling(
                                df, Region, Market, Brand, y_variable, media_variables, other_variables, non_scaled_variables,
                                growth_rates, carryover_rates, midpoints, powers,
                                model_type, standardization_method, transformation_type, apply_same_params,
                                current_media_idx + 1, current_transformations + [(co, pw)], results, model_counter,
                                same_carryover, None, own_media_variables, fixed_midpoint
                            )

            return results
                    
            # media_var = media_variables[current_media_idx]

            # # media_var = media_variables[current_media_idx]

            # if apply_same_params == "Yes":
            #     if transformation_type == "logistic":
            #         if not growth_rates or not carryover_rates or not midpoints:
            #             return results
            #         gr = growth_rates[0]
            #         co = carryover_rates[0]
            #         mp = midpoints[0]
            #         transformations = [(gr, co, mp)] * len(media_variables)
            #         return recursive_modeling(
            #             df, Region, Market, Brand, y_variable, media_variables, other_variables, non_scaled_variables,
            #             growth_rates, carryover_rates, midpoints, powers,
            #             model_type, standardization_method, transformation_type, apply_same_params,
            #             len(media_variables), transformations, results, model_counter
            #         )

            #     elif transformation_type == "power":
            #         if not carryover_rates or not powers:
            #             return results
            #         co = carryover_rates[0]
            #         pw = powers[0]
            #         transformations = [(co, pw)] * len(media_variables)
            #         return recursive_modeling(
            #             df, Region, Market, Brand, y_variable, media_variables, other_variables, non_scaled_variables,
            #             growth_rates, carryover_rates, midpoints, powers,
            #             model_type, standardization_method, transformation_type, apply_same_params,
            #             len(media_variables), transformations, results, model_counter
            #         )

            # else:
            #     if same_carryover == "Yes":
            #         for co in carryover_rates:
            #             if transformation_type == "logistic":
            #                 for gr in growth_rates:
            #                     for mp in midpoints:
            #                         results = recursive_modeling(
            #                             df, Region, Market, Brand, y_variable, media_variables, other_variables, non_scaled_variables,
            #                             growth_rates, carryover_rates, midpoints, powers,
            #                             model_type, standardization_method, transformation_type, apply_same_params,
            #                             current_media_idx + 1, current_transformations + [(gr, co, mp)], results, model_counter,
            #                             same_carryover=same_carryover, fixed_carryover=co
            #                         )

            #             elif transformation_type == "power":
            #                 for pw in powers:
            #                     results = recursive_modeling(
            #                         df, Region, Market, Brand, y_variable, media_variables, other_variables, non_scaled_variables,
            #                         growth_rates, carryover_rates, midpoints, powers,
            #                         model_type, standardization_method, transformation_type, apply_same_params,
            #                         current_media_idx + 1, current_transformations + [(co, pw)], results, model_counter,
            #                         same_carryover=same_carryover, fixed_carryover=co
            #                     )

            #     else:  # 🚩 Correct structure for "NO" same_carryover
            #         if transformation_type == "logistic":
            #             for gr in growth_rates:
            #                 for co in carryover_rates:
            #                     for mp in midpoints:
            #                         results = recursive_modeling(
            #                             df, Region, Market, Brand, y_variable, media_variables, other_variables, non_scaled_variables,
            #                             growth_rates, carryover_rates, midpoints, powers,
            #                             model_type, standardization_method, transformation_type, apply_same_params,
            #                             current_media_idx + 1, current_transformations + [(gr, co, mp)], results, model_counter,
            #                             same_carryover=same_carryover, fixed_carryover=None
            #                         )

            #         elif transformation_type == "power":
            #             for co in carryover_rates:
            #                 for pw in powers:
            #                     results = recursive_modeling(
            #                         df, Region, Market, Brand, y_variable, media_variables, other_variables, non_scaled_variables,
            #                         growth_rates, carryover_rates, midpoints, powers,
            #                         model_type, standardization_method, transformation_type, apply_same_params,
            #                         current_media_idx + 1, current_transformations + [(co, pw)], results, model_counter,
            #                         same_carryover=same_carryover, fixed_carryover=None
            #                     )


            # return results
        def generalized_modeling_recursive(
            df, Region, Market, Brand, y_variables, media_variables, other_variables, non_scaled_variables,
            growth_rates, carryover_rates, midpoints, powers, model_types, standardization_method,
            transformation_type, apply_same_params, checkpoint_path,
            same_carryover=True,
            own_media_variables=['TV_Reach', 'Digital_Reach', 'AllMedia_Reach'],  # Pass your brand media here
            fixed_midpoint=0  # Fixed midpoint for competitor media
        ):
            results = []
            model_counter = 1
            import os

            if os.path.exists(checkpoint_path):
                st.warning(f"Checkpoint found at {checkpoint_path}. Resuming from the last saved state.")
                results_df = pd.read_csv(checkpoint_path)
                results = results_df.to_dict('records')
                model_counter = len(results) + 1
            else:
                st.info("No checkpoint found. Starting fresh...")

            total_models = len(Brand) * len(model_types) * len(y_variables) * (1 + len(Region))
            progress_bar = st.progress(0)
            progress_step = 1 / total_models if total_models > 0 else 1

            models_completed = 0

            for brand in Brand:
                st.write(f"Processing brand: {brand}")

                for model_type in model_types:
                    st.write(f"  Running {model_type} models...")

                    for y_variable in y_variables:
                        st.write(f"    Modeling for dependent variable: {y_variable}")

                        for co in carryover_rates:
                            try:
                                results = recursive_modeling(
                                    df, Region, Market, brand, y_variable, media_variables, other_variables, non_scaled_variables,
                                    growth_rates, [co], midpoints, powers,
                                    model_type, standardization_method, transformation_type, apply_same_params=apply_same_params,
                                    current_media_idx=0, current_transformations=[], results=results, model_counter=model_counter,
                                    same_carryover=same_carryover, fixed_carryover=co,
                                    own_media_variables=own_media_variables, fixed_midpoint=fixed_midpoint
                                )
                                model_counter += 1
                                models_completed += 1
                                progress_bar.progress(min(models_completed * progress_step, 1.0))

                                pd.DataFrame(results).to_csv(checkpoint_path, index=False)
                                st.success(f"Checkpoint saved after model {model_counter - 1} at {checkpoint_path}.")

                            except Exception as e:
                                st.error(f"Error in stacked model for brand {brand}, y {y_variable}, model {model_type}: {e}")
                                continue

                            for region in Region:
                                st.write(f"    Running region-specific model for Region: {region}")

                                try:
                                    results = recursive_modeling(
                                        df, [region], Market, brand, y_variable, media_variables, other_variables, non_scaled_variables,
                                        growth_rates, [co], midpoints, powers,
                                        model_type, standardization_method, transformation_type, apply_same_params=apply_same_params,
                                        current_media_idx=0, current_transformations=[], results=results, model_counter=model_counter,
                                        same_carryover=same_carryover, fixed_carryover=co,
                                        own_media_variables=own_media_variables, fixed_midpoint=fixed_midpoint
                                    )
                                    model_counter += 1
                                    models_completed += 1
                                    progress_bar.progress(min(models_completed * progress_step, 1.0))

                                    pd.DataFrame(results).to_csv(checkpoint_path, index=False)
                                    st.success(f"Checkpoint saved after model {model_counter - 1} at {checkpoint_path}.")

                                except Exception as e:
                                    st.error(f"Error in region-specific model for brand {brand}, y {y_variable}, region {region}, model {model_type}: {e}")
                                    continue

            st.success("All models completed!")
            final_results_df = pd.DataFrame(results)
            return final_results_df



        st.markdown(
                    """ 
                    <div style="height: 3px; background-color: black; margin: 15px 0;"></div>
                    """, 
                    unsafe_allow_html=True
                    )


        st.markdown(
                        """
                        <style>
                            div.stTabs button {
                                flex-grow: 1;
                                text-align: center;
                            }
                        </style>
                        """,
                        unsafe_allow_html=True
                    )


        st.markdown("""
            <style>


            /* Make the tab text bolder */
            div.stTabs button div p {
                font-weight: 900 !important; /* Maximum boldness */
                font-size: 18px !important; /* Slightly larger text */
                color: black !important; /* Ensuring good contrast */
            }
            </style>
        """, unsafe_allow_html=True)

        # Initialize session state keys for Bottom-Up and Top-Down models
        for key in [
            "Bottom up1", "Bottom up2", "Bottom up3", "Bottom up4", #"Bottom up5", 
            "Bottom up6", "Bottom up7","Bottom up8","Bottom up9", "Bottom up11", "Bottom up12", "Bottom up13","Bottom up14",
            "Top down1", "Top down2", "Top down3", "Top down4", #"Top down5", 
            "Top down6", "Top down7","Top down8","Top down9", "Top down11", "Top down12", "Top down13", "Top down14"
        ]:
            if key not in st.session_state:
                st.session_state[key] = []

        if "selections" not in st.session_state:
            st.session_state["selections"] = {}

        def update_selections(model_key):
            """Update session state with selections from the Bottom-Up model."""
            st.session_state["selections"] = {
                "regions": st.session_state[f"{model_key}1"],
                "markets": st.session_state[f"{model_key}2"],
                "brands": st.session_state[f"{model_key}3"],
                "y_variables": st.session_state[f"{model_key}4"],
                # "media_variables": st.session_state[f"{model_key}5"],
                "other_variables": st.session_state[f"{model_key}6"],
                "non_scaled_variables": st.session_state[f"{model_key}7"],
                "growth_rates": st.session_state[f"{model_key}11"],
                "carryover_rates": st.session_state[f"{model_key}12"],
                "midpoints": st.session_state[f"{model_key}13"],
                "model_types": st.session_state.get(f"{model_key}8", ["Generalized Constrained Ridge"]),
                "standardization_method": st.session_state.get(f"{model_key}9", "minmax"),
                "apply_same_params": st.session_state["apply_params_media"],
                "transformation_type": st.session_state["transformation_type"],
                "powers": st.session_state[f"{model_key}14"]
            }


        tab1,tab2,tab3,tab4 = st.tabs(["Bottom up Model","Top down Model","Final Result","ROI"])

        with tab1:
            import streamlit as st
            import pandas as pd

            # Page title
            # st.title("Modeling Options")

            with st.expander("#### Modeling Options", expanded=False):

                col1, col2, col3 = st.columns(3)
                # Extract unique values for dynamic dropdowns
                available_regions = df["Region"].unique().tolist()
                available_markets = df["Market"].unique().tolist()
                available_brands = df["Brand"].unique().tolist()

                with col1:
                    # Region selection
                    regions = st.multiselect("Select Regions", available_regions, key="Bottom up1")  #default=available_regions,

                with col2:
                    # Market selection
                    markets = st.multiselect("Select Markets", available_markets, key="Bottom up2")  #default=available_markets,

                with col3:
                    # Brand selection
                    brands = st.multiselect("Select Brands", available_brands, key="Bottom up3")  #default=available_brands,

                col4, col5, col6, col7 = st.columns(4)

                with col4:
                    # Dependent variable selection
                    y_variables = st.multiselect("Select Dependent Variable (y)", df.columns.tolist(),key="Bottom up4")  #, default=["Filtered Volume Index"]

                with col5:
                    # Media variables selection
                    media_variables = st.multiselect(
                        "Select Genre Media Variables", df.columns.tolist(),key="Bottom up5"
                    # default=['Digital_Total_Unique_Reach', 'TV_Total_Unique_Reach']
                    )

                with col6:
                    # Other variables selection
                    other_variables = st.multiselect(
                        "Select Other Variables", df.columns.tolist(),key="Bottom up6"
                        #default=['D1', 'Price', 'A&P_Amount_Spent', 'Region_Brand_seasonality']
                    )

                with col7:
                    non_scaled_variables = st.multiselect(
                        "Select Other Non Scaled Variables", df.columns.tolist(), 
                        default=[],key="Bottom up7"
                    )
            


                import streamlit as st
                    
                def parse_input(input_str, default=[]):
                    try:
                        if not input_str:
                            return default
                        return [float(i.strip()) for i in str(input_str).split(",") if i.strip()]
                    except Exception as e:
                        st.warning(f"Input parsing error: {e}")
                        return default


                col8, col9, col10 = st.columns(3)

                with col8:
                    # Transformation type selection (first, because later inputs depend on it)
                    transformation_type = st.selectbox(
                        "Select Transformation Type", 
                        ["logistic", "power"], 
                        index=0, 
                        key="transformation_type"
                    )

                    if transformation_type == "logistic":
                    #     # User input for Growth Rate
                    #     growth_input = st.text_area("Enter Growth Rates (comma-separated)", "3.5", key="Bottom up11")
                    #     growth_rates = parse_input(growth_input)
                    # else:
                    #     growth_rates = []  # or None
                        # User input for Growth Rate with validation
                        growth_input = st.text_area(
                            "Enter Growth Rates (comma-separated)", 
                            value=str("3.5"),
                            help="Enter comma-separated values like '3.5' or '3.5,4.0'",
                            key="Bottom up11"
                        )
                        growth_rates = parse_input(growth_input, [3.5])
                    else:
                        growth_rates = []

                    # Model types selection
                    model_types = st.multiselect(
                        "Select Model Types", 
                        ["Generalized Constrained Ridge", "Ridge", "Linear Regression", "Lasso", "Elastic Net"], 
                        default=["Generalized Constrained Ridge"], 
                        key="Bottom up8"
                    )

                with col9:
                    # # User input for Carryover Rate (always needed)
                    # carryover_input = st.text_area("Enter Carryover Rates (comma-separated)", "0.8", key="Bottom up12")
                    # carryover_rates = parse_input(carryover_input)
                    # User input for Carryover Rate with validation
                    carryover_input = st.text_area(
                        "Enter Carryover Rates (comma-separated)", 
                        value=str("0.8"),
                        help="Enter comma-separated values like '0.8' or '0.8,0.6'",
                        key="Bottom up12"
                    )
                    carryover_rates = parse_input(carryover_input, [0.8])

                    # Standardization method selection
                    standardization_method = st.selectbox(
                        "Select Standardization Method", 
                        ['minmax', 'zscore', 'none'], 
                        index=0, 
                        key="Bottom up9"
                    )

                    checkpoint_path = st.text_input(
                        "Enter Checkpoint File Path",
                        value="model_results_checkpoint.csv",  # default filename
                        help="Enter full path like 'C:/Users/Name/Documents/checkpoint.csv' or just filename to save in current folder",
                        key="Bottom up_checkpoint"
                    ) 

                with col10:
                    if transformation_type == "logistic":
                    #     # User input for Midpoints
                    #     midpoint_input = st.text_area("Enter Midpoints (comma-separated)", "0", key="Bottom up13")
                    #     midpoints = parse_input(midpoint_input)
                    #     powers = []  # Empty, not needed
                    # else:
                    #     # User input for Powers
                    #     power_input = st.text_area("Enter Powers (comma-separated)", "0.5", key="Bottom up14")
                    #     powers = parse_input(power_input)
                    #     midpoints = []  # Empty, not needed
                        # User input for Midpoints with validation
                        midpoint_input = st.text_area(
                            "Enter Midpoints (comma-separated)", 
                            value=str("0"),
                            help="Enter comma-separated values like '0' or '0,0.5'",
                            key="Bottom up13"
                        )
                        midpoints = parse_input(midpoint_input, [0])
                        powers = []
                    else:
                        # User input for Powers with validation
                        power_input = st.text_area(
                            "Enter Powers (comma-separated)", 
                            value=str("0.5"),
                            help="Enter comma-separated values like '0.5' or '0.5,1.0'",
                            key="Bottom up14"
                        )
                        powers = parse_input(power_input, [0.5])
                        midpoints = []

                    # Option to apply same parameters across all media variables
                    apply_same_params = st.selectbox(
                        "Apply same parameters across all media variables", 
                        ["Yes", "No"], 
                        index=0, 
                        key="apply_params_media"
                    )

                    same_carryover = st.selectbox(
                        "Apply same carryover across all media variables", 
                        ["Yes", "No"], 
                        index=0, 
                        key="apply_same_carryover"
                    )

               


        # Save selections when Bottom-Up Model runs
            # if st.button("Run Bottom-Up Model"):
            #     update_selections("Bottom up")
            from datetime import datetime

            # Run modeling button
            if st.button("Run Bottom-Up Model", key="bottom up model"):
                update_selections("Bottom up")
                st.write("Running model with the selected options...")
                # Record start time
                start_time = datetime.now()
                st.write(f"Model run started at: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")

                
                # Call the modeling function with selected parameters
                results_df = generalized_modeling_recursive(
                    df=df,
                    Region=regions,
                    Market=markets,
                    Brand=brands,
                    y_variables=y_variables,
                    media_variables=media_variables,
                    other_variables=other_variables,
                    non_scaled_variables = non_scaled_variables,
                    growth_rates=growth_rates,
                    carryover_rates=carryover_rates,
                    midpoints=midpoints,
                    model_types=model_types,
                    standardization_method=standardization_method,
                    apply_same_params=apply_same_params,
                    same_carryover = same_carryover,
                    transformation_type=transformation_type,
                    powers=powers,
                    checkpoint_path=checkpoint_path  # Pass the user-specified path
                )
                
                st.write("Modeling completed!")
                st.dataframe(results_df)  # Display results

                # Record end time
                end_time = datetime.now()
                st.write(f"Model run ended at: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")

                # Calculate and display duration
                duration = end_time - start_time
                st.write(f"Total time taken: {duration}")

                # Store results_df in session_state
                st.session_state["results_df"] = results_df
                
            # st.dataframe(results_df)  # Display results
            # else:
            #     st.warning("Please upload a CSV file to proceed.")
            # Check if the variable is in session_state
            if "results_df" in st.session_state and st.session_state["results_df"] is not None:
                st.dataframe(st.session_state["results_df"])  # Display results
                results_df = st.session_state["results_df"]

            else:
                uploaded_file = st.file_uploader("Upload the results file (CSV or Excel)", type=["csv", "xlsx"])

                if uploaded_file is not None:
                    # Read file based on its extension
                    if uploaded_file.name.endswith(".csv"):
                        results_df = pd.read_csv(uploaded_file)
                    else:
                        results_df = pd.read_excel(uploaded_file)

                    # Save to session state
                    st.session_state["results_df"] = results_df

                    st.success("File uploaded and stored successfully!")
                    st.dataframe(results_df)

            # st.write("gsgh")


            if "expanded_results_df" not in st.session_state:
                st.session_state["expanded_results_df"] = None  # or pd.DataFrame() if applicable

            if st.button("Final Result df", key="bottom up result"):
                if "results_df" not in st.session_state:
                    st.warning("Please run the model first by clicking 'Run Model'.")
                else:
                    results_df = st.session_state["results_df"]  # Retrieve stored results

                    expanded_results = []

                    # Loop through each model in the results dataframe
                    for _, model_row in results_df.iterrows():
                        # Extract model type and Region
                        model_type = model_row['Model_type']
                        original_region = model_row.get('Region', None)  # Get the original region from the results dataframe

                        # Determine if the model is stacked
                        is_stacked = model_type.startswith("Stacked")

                        # Extract feature names and parameters dynamically
                        feature_names = [
                            col.split('beta_')[1] for col in model_row.keys() if col.startswith('beta_')
                        ]
                        model = {
                            "b": model_row['beta0'],
                            "W": np.array([model_row[f'beta_{col}'] for col in feature_names]),
                        }

                        

                        # Handle stacked models
                        if is_stacked:
                            # Extract regions dynamically
                            Region = [col.split('Region_')[1] for col in feature_names if col.startswith('Region_')]

                            # Parse Region_MAPEs into a dictionary
                            region_mapes = {
                                region_mape.split(':')[0]: float(region_mape.split(':')[1])
                                for region_mape in model_row['Region_MAPEs'].split(',')
                            }

                            region_y_means = {
                                region_y_mean.split(':')[0]: float(region_y_mean.split(':')[1])
                                for region_y_mean in model_row['Region_Y_means'].split(',')
                            }

                            

                            # # Extract means of variables for each region from the results_df
                            # variable_means = {
                            #     var: {
                            #         region_mean.split(':')[0]: float(region_mean.split(':')[1])
                            #         for region_mean in model_row[f"{var}_mean"].split(',')
                            #     }
                            #     for var in feature_names if f"{var}_mean" in model_row
                            # }
                            # Extract means of variables for all regions from the results_df
                            # variable_means = {}
                            # for col in model_row.keys():
                            #     if col.endswith("_mean"):
                            #         variable_name = col.replace("_mean", "")
                            #         variable_means[variable_name] = {
                            #             region_mean.split(':')[0]: float(region_mean.split(':')[1])
                            #             for region_mean in model_row[col].split(',')
                            #         }
                            # variable_means = {}
                            # for col in model_row.keys():
                            #     if col.endswith("_mean"):
                            #         variable_name = col.replace("_mean", "")
                            #         col_value = model_row[col]
                                    
                            #         if isinstance(col_value, str):
                            #             variable_means[variable_name] = {
                            #                 region_mean.split(':')[0]: float(region_mean.split(':')[1])
                            #                 for region_mean in col_value.split(',')
                            #             }
                            #         else:
                            #             # Optional: handle non-string case, e.g., float directly assigned to a default region
                            #             variable_means[variable_name] = {"default": float(col_value)}
                            # Extract means of variables for all regions from the results_df
                            # variable_means = {}
                            # for col in model_row.keys():
                            #     if col.endswith("_mean") and isinstance(model_row[col], str):
                            #         variable_name = col.replace("_mean", "")
                            #         variable_means[variable_name] = {
                            #             item.split(':')[0].strip(): float(item.split(':')[1])
                            #             for item in model_row[col].split(',')
                            #             if ':' in item
                            #         }


                            # variable_range = {}
                            # for col in model_row.keys():
                            #     if col.endswith("_range"):
                            #         variable_name = col.replace("_range", "")
                            #         col_value = model_row[col]
                                    
                            #         if isinstance(col_value, str):
                            #             variable_range[variable_name] = {
                            #                 region_mean.split(':')[0]: float(region_mean.split(':')[1])
                            #                 for region_mean in col_value.split(',')
                            #             }
                            #         else:
                            #             # Optional: handle non-string case, e.g., float directly assigned to a default region
                            #             variable_range[variable_name] = {"default": float(col_value)}

                            # def parse_region_mapping(col_value):
                            #     """
                            #     Parse a string like "Andhra-Telangana:10.7, Assam-NE:7.1"
                            #     into a dict { "Andhra-Telangana": 10.7, "Assam-NE": 7.1 }
                            #     """
                            #     if isinstance(col_value, str):
                            #         return {
                            #             item.split(':')[0].strip(): float(item.split(':')[1])
                            #             for item in col_value.split(',') if ':' in item
                            #         }
                            #     return {}
                            
                            def parse_region_mapping(col_value):
                                """
                                Safely parse strings like:
                                    "Andhra-Telangana:0.047922, Assam-NE:0.02388, ..."
                                into a dictionary while skipping NA / invalid values.
                                """
                                if not isinstance(col_value, str):
                                    return {}

                                mapping = {}

                                for item in col_value.split(','):
                                    if ':' not in item:
                                        continue

                                    key, val = item.split(':', 1)
                                    key = key.strip()
                                    val = val.strip()

                                    # Skip NA or empty values
                                    if val.upper() in ["NA", "N/A", "", "NONE", "NULL"]:
                                        continue

                                    try:
                                        mapping[key] = float(val)
                                    except Exception:
                                        # Skip values that still fail
                                        continue

                                return mapping


                            variable_means, variable_std, variable_range, variable_sensitivity = {}, {}, {}, {}

                            for col in model_row.keys():
                                if col.endswith("_mean"):
                                    variable_name = col.replace("_mean", "")
                                    variable_means[variable_name] = parse_region_mapping(model_row[col])
                                elif col.endswith("_std"):
                                    variable_name = col.replace("_std", "")
                                    variable_std[variable_name] = parse_region_mapping(model_row[col])
                                elif col.endswith("_range"):
                                    variable_name = col.replace("_range", "")
                                    variable_range[variable_name] = parse_region_mapping(model_row[col])
                                elif col.endswith("_sensitivity"):
                                    variable_name = col.replace("_sensitivity", "")
                                    variable_sensitivity[variable_name] = parse_region_mapping(model_row[col])



                            # st.write("variable_range :", variable_range)

                            # Loop through each region
                            for region in Region:
                                # Extract base intercept and region-specific intercept
                                base_intercept = model["b"]
                                region_intercept = (
                                    model["W"][feature_names.index(f"Region_{region}")] if f"Region_{region}" in feature_names else 0
                                )
                                adjusted_intercept = base_intercept + region_intercept

                                # Calculate adjusted betas
                                adjusted_betas = {}
                                for var in feature_names:
                                    # Skip interaction terms (variables starting with {region}_interaction_)
                                    if not var.startswith("Region_") and not any(var.startswith(f"{region}_interaction") for region in Region):
                                        # Base coefficient for the variable
                                        base_beta = model["W"][feature_names.index(var)]

                                        # Interaction term adjustment (if exists)
                                        interaction_term = f"{region}_interaction_{var}"
                                        interaction_beta = (
                                            model["W"][feature_names.index(interaction_term)]
                                            if interaction_term in feature_names else 0
                                        )

                                        # Store adjusted beta
                                        adjusted_betas[var] = base_beta + interaction_beta

                       
                                # # Prepare the variable-specific mean strings for this region
                                # region_variable_means = {
                                #     f"{var}_mean": means.get(region, None)
                                #     for var, means in variable_means.items()
                                # }
                                # # st.warning(f"region_variable_means: {region_variable_means}")
                                # region_variable_range = {
                                #     f"{var}_mean": means.get(region, None)
                                #     for var, means in variable_range.items()
                                # }
                                # st.write(f"region_variable_range: {region_variable_range}")

                                region_variable_means = {f"{var}_mean": means.get(region, None) 
                                                        for var, means in variable_means.items()}

                                region_variable_std = {f"{var}_std": stds.get(region, None) 
                                                        for var, stds in variable_std.items()}

                                region_variable_range = {f"{var}_range": ranges.get(region, None) 
                                                        for var, ranges in variable_range.items()}

                                region_variable_sensitivity = {f"{var}_sensitivity": sens.get(region, None) 
                                                            for var, sens in variable_sensitivity.items()}

                                # Build the expanded result dict
                                region_row = {
                                    'Model_num': model_row['Model_num'],
                                    'Model_type': model_row['Model_type'],
                                    'Market': model_row['Market'],
                                    'Brand': model_row['Brand'],
                                    'Region': region,
                                    'Model_selected': model_row['Model_selected'],
                                    'MAPE': model_row['MAPE'],
                                    'Avg_MAPE': model_row['Avg_MAPE'],
                                    "Region_MAPEs":region_mapes.get(region, None),
                                    'R_squared': model_row['R_squared'],
                                    'Adjusted_R_squared': model_row['Adjusted_R_squared'],
                                    'AIC': model_row['AIC'],
                                    'BIC': model_row['BIC'],
                                    'Y': model_row['Y'],
                                    'Region_Y_means': region_y_means.get(region, None),  # Assign region-specific Y mean
                                    # 'Y_mean': model_row['Y_mean'],
                                    'beta0': adjusted_intercept,
                                    **{f'beta_{var}': adjusted_betas[var] for var in adjusted_betas.keys()},
                                    **region_variable_means,         # ✅ add all _mean values
                                    **region_variable_std,          # ✅ add all _std values
                                    **region_variable_range,         # ✅ add all _range values
                                    **region_variable_sensitivity,   # ✅ add all _sensitivity values
                                    'Transformation_type': model_row.get('Transformation_type', "logistic"),   # default logistic
                                    'Transformation_params': model_row.get('Transformation_params', ""),  # safe default
                                    'Standardization_method': model_row.get('Standardization_method', 'minmax')
                                }

                                # Add Transformation-specific columns
                                if model_row.get('Transformation_type') == "logistic":
                                    region_row.update({
                                        'Growth_rate': model_row.get('Growth_rate', ''),
                                        'Carryover': model_row.get('Carryover', ''),
                                        'Mid_point': model_row.get('Mid_point', '')
                                    })
                                elif model_row.get('Transformation_type') == "power":
                                    region_row.update({
                                        'Carryover': model_row.get('Carryover', ''),
                                        'Power': model_row.get('Power', '')
                                    })

                                # Append the region-specific row
                                expanded_results.append(region_row)
                        else:
                            # For non-stacked models, retain the original row
                            region_row = model_row.to_dict()  # Convert the row to a dictionary
                        
                            
                            expanded_results.append(region_row)

                    # Replace the original results with the expanded results
                    # Add a unique identifier to each row
                    expanded_results_df = pd.DataFrame(expanded_results)  # Convert to DataFrame for further use
                    st.dataframe(expanded_results_df)
                    # Replace None values in 'Region_MAPEs' with the corresponding 'MAPE' values
                    expanded_results_df['Region_MAPEs'] = expanded_results_df.apply(
                        lambda row: row['MAPE'] if pd.isna(row['Region_MAPEs']) or row['Region_MAPEs'] in ["None", "nan", ""] else row['Region_MAPEs'],
                        axis=1
                    )

                    # Make sure 'None' values are actual NaNs
                    expanded_results_df['Region_Y_means'] = expanded_results_df['Region_Y_means'].replace('None', np.nan)

                    # # Check types
                    # st.write(expanded_results_df['Brand'].apply(type).value_counts())
                    # st.write(expanded_results_df['Region'].apply(type).value_counts())
                    expanded_results_df['Region'] = expanded_results_df['Region'].apply(
                            lambda x: x[0] if isinstance(x, list) else x
                        )


                    # Fill NaNs using Brand + Region group means
                    expanded_results_df['Region_Y_means'] = expanded_results_df.groupby(['Brand', 'Region'])['Region_Y_means'].transform(lambda x: x.fillna(method='ffill').fillna(method='bfill'))


                    

            
                    import re
                    
                    
                    # def clean_to_number(text):
                    #     try:
                    #         # Extract the first valid number (float or int) from the string
                    #         match = re.search(r'\d+\.\d+|\d+', str(text))
                    #         return float(match.group()) if match else None
                    #     except:
                    #         return None

                    def clean_to_number(text):
                        try:
                            if ":" in str(text):
                                val = text.split(":", 1)[1].strip()
                            else:
                                val = str(text).strip()

                            return float(val)
                        except:
                            return None

                    def clean_to_number_by_region(region):
                        def inner(text):
                            try:
                                parts = str(text).split(',')
                                for part in parts:
                                    key_val = part.strip().split(':')
                                    if len(key_val) == 2 and key_val[0].strip() == region:
                                        return float(key_val[1])
                            except:
                                return None
                        return inner
                        
                    expanded_results_df['Region_Y_means'] = expanded_results_df['Region_Y_means'].apply(clean_to_number)

                    # for col in expanded_results_df.columns:
                    #     if col.endswith("_mean") and expanded_results_df[col].dtype == object:
                    #         expanded_results_df[col] = expanded_results_df[col].apply(clean_to_number)
                    #         expanded_results_df[col] = expanded_results_df.groupby(['Brand', 'Region'])[col].transform(
                    #             lambda x: x.fillna(method='ffill').fillna(method='bfill')
                    #         )

                    for col in expanded_results_df.columns:
                        if col.endswith("_mean") and expanded_results_df[col].dtype == object:
                            # expanded_results_df[col] = expanded_results_df.apply(
                            #     lambda row: clean_to_number_by_region(row["Region"])(row[col]),
                            #     axis=1
                            # )
                            expanded_results_df[col] = expanded_results_df[col].apply(clean_to_number)
                            expanded_results_df[col] = expanded_results_df.groupby(['Brand', 'Region'])[col].transform(
                                lambda x: x.fillna(method='ffill').fillna(method='bfill')
                            )

                    for col in expanded_results_df.columns:
                        if col.endswith("_std") and expanded_results_df[col].dtype == object:
                            expanded_results_df[col] = expanded_results_df[col].apply(clean_to_number)
                            expanded_results_df[col] = expanded_results_df.groupby(['Brand', 'Region'])[col].transform(
                                lambda x: x.fillna(method='ffill').fillna(method='bfill')
                            ).astype(float)

                    # st.dataframe(expanded_results_df)


                    for col in expanded_results_df.columns:
                        if col.endswith("_sensitivity") and expanded_results_df[col].dtype == object:
                            expanded_results_df[col] = expanded_results_df[col].apply(clean_to_number)
                            expanded_results_df[col] = expanded_results_df.groupby(['Brand', 'Region'])[col].transform(
                                lambda x: x.fillna(method='ffill').fillna(method='bfill')
                            ).astype(float)

                    # st.dataframe(expanded_results_df)

                    for col in expanded_results_df.columns:
                        if col.endswith("_range"): #and expanded_results_df[col].dtype == object:
                            # expanded_results_df[col] = expanded_results_df.apply(
                            #     lambda row: clean_to_number_by_region(row["Region"])(row[col]),
                            #     axis=1
                            # )
                            expanded_results_df[col] = expanded_results_df[col].apply(clean_to_number)
                            expanded_results_df[col] = expanded_results_df.groupby(['Brand', 'Region'])[col].transform(
                                lambda x: x.fillna(method='ffill').fillna(method='bfill')
                            )
                            
                    st.dataframe(expanded_results_df)

                    # Loop through all beta columns and compute contribution
                    # for col in expanded_results_df.columns:
                    #     if col.startswith('beta_'):
                    #         var_name = col.replace('beta_', '')  # get the variable name
                    #         mean_col = f"{var_name}_mean"
                    #         # st.write(mean_col)
                            
                    #         if mean_col in expanded_results_df.columns:
                    #             contribution_col = f"{var_name}_contribution"
                    #             expanded_results_df[contribution_col] = expanded_results_df[col] * expanded_results_df[mean_col]
                    # Loop through all beta columns and compute contribution
                    for col in expanded_results_df.columns:
                        if col.startswith('beta_scaled_'):
                            var_name = col.replace('beta_scaled_', '')  # get the variable name
                            mean_col = f"{var_name}_mean"
                            range_col = f"{var_name}_range"
                            std_col = f"{var_name}_std"
                            # st.write(range_col)
                            # st.write(col)
                            if expanded_results_df["Standardization_method"].iloc[0] == "zscore":
                                non_scaled_beta = f"beta_non_scaled_{var_name}"
                                expanded_results_df[non_scaled_beta] = expanded_results_df[col] / expanded_results_df[std_col]
                            
                            if expanded_results_df["Standardization_method"].iloc[0] == "minmax":
                                contribution_col = f"{var_name}_contribution"
                                non_scaled_beta = f"beta_non_scaled_{var_name}"
                                expanded_results_df[contribution_col] = expanded_results_df[col] * expanded_results_df[mean_col] * expanded_results_df[range_col]
                                # expanded_results_df[non_scaled_beta] = expanded_results_df[col] * expanded_results_df[range_col]

                    # --- Now compute non-scaled intercept (beta0) ---
                    if expanded_results_df["Standardization_method"].iloc[0] == "zscore":
                        beta0_scaled = expanded_results_df["beta0"]

                        # sum over all scaled betas * mean/std
                        adjustment = 0
                        for col in expanded_results_df.columns:
                            if col.startswith('beta_scaled_'):
                                var_name = col.replace('beta_scaled_', '')
                                mean_col = f"{var_name}_mean"
                                std_col = f"{var_name}_std"
                                adjustment += expanded_results_df[col] * (expanded_results_df[mean_col] / expanded_results_df[std_col])

                        expanded_results_df["beta0_non_scaled"] = beta0_scaled - adjustment

                    # # Loop through all beta columns and compute contribution
                    # for col in expanded_results_df.columns:
                    #     if col.startswith('beta_scaled_'):
                    #         var_name = col.replace('beta_scaled_', '')  # get the variable name
                    #         mean_col = f"{var_name}_mean"
                    #         range_col = f"{var_name}_range"
                    #         # st.write(range_col)
                    #         # st.write(col)
                            
                    #         if mean_col in expanded_results_df.columns:
                    #             contribution_col = f"{var_name}_contri"
                    #             non_scaled_beta = f"beta_non_sclaed_{var_name}"
                    #             # expanded_results_df[contribution_col] = expanded_results_df[col] * expanded_results_df[mean_col] * expanded_results_df[range_col]
                    #             expanded_results_df[non_scaled_beta] = expanded_results_df[col] * expanded_results_df[range_col]

                    # Step 2: Collect all contribution columns (excluding beta0 for now)
                    # contribution_cols = [col for col in expanded_results_df.columns if col.endswith('_contri')]
                    contribution_cols = [col for col in expanded_results_df.columns if col.endswith('_contribution')]
                    # st.write("Contribution columns:", contribution_cols)

                    # # Step 3: Add intercept (beta0) as its own contribution
                    # expanded_results_df['beta0_contribution'] = expanded_results_df['beta0']
                    # contribution_col.append('beta0_contribution')

                    # Step 4: Calculate total contribution
                    # expanded_results_df['total_contribution'] = expanded_results_df[contribution_col].sum(axis=1)

                    # Step 5: Compute percentage contribution for each variable
                    for col in contribution_cols:
                        pct_col = col.replace('_contribution', '_elasticity')
                        # st.write(expanded_results_df[col])
                        expanded_results_df[pct_col] = expanded_results_df[col] / expanded_results_df['Region_Y_means']

                    # st.write(expanded_results_df.columns.tolist())

                    # # Loop through all media variables
                    # for var in media_variables:
                    #     pct_col = f"{var}_transformed_pct_contribution"
                    #     slope_col = f"{var}_sensitivity"
                    #     adj_col = f"{var}_elasticity"

                    #     # Multiply % contribution by its slope
                    #     expanded_results_df[adj_col] = expanded_results_df[pct_col] * expanded_results_df[slope_col]

                  
                    # media_variables = [col.replace("beta_", "").replace("_transformed", "") 
                    #                 for col in expanded_results_df.columns 
                    #                 if col.startswith('beta_') and col.endswith('_transformed')]

                    for i, var in enumerate(media_variables):
                        beta_col = f'beta_{var}_transformed'
                        sensitivity_col = f'{var}_sensitivity'
                        elasticity_col = f'{var}_elasticity'


                        # Safely parse the i-th growth rate and carryover from comma-separated strings
                        expanded_results_df[f'{var}_growth_rate'] = expanded_results_df['Growth_rate'].apply(
                            lambda x: float(x.split(',')[i]) if isinstance(x, str) and len(x.split(',')) > i else np.nan
                        ).astype(float)
                        expanded_results_df[f'{var}_carryover'] = expanded_results_df['Carryover'].apply(
                            lambda x: float(x.split(',')[i]) if isinstance(x, str) and len(x.split(',')) > i else np.nan
                        ).astype(float)

                        # st.dataframe(expanded_results_df)

                        # st.write(expanded_results_df[[beta_col, sensitivity_col, f'{var}_growth_rate', f'{var}_carryover', 'Region_Y_means']])

                        # Now compute the elasticity using the provided formula
                        expanded_results_df[elasticity_col] = (
                            expanded_results_df[beta_col]
                            * expanded_results_df[f'{var}_growth_rate']
                            * expanded_results_df[sensitivity_col]
                        ) / (
                            (1 - expanded_results_df[f'{var}_carryover']) * expanded_results_df['Region_Y_means']
                        )

                    # st.dataframe(expanded_results_df)


                    # Extract the region name only if it's in list format, otherwise keep the original value
                    expanded_results_df['Region'] = expanded_results_df['Region'].astype(str).apply(
                        lambda x: re.findall(r"\['(.*?)'\]", x)[0] if re.findall(r"\['(.*?)'\]", x) else x
                    )


                    expanded_results_df['Unique_ID'] = range(1, len(expanded_results_df) + 1)  # Assign unique IDs starting from 1
                    # expanded_results_df["Approach"] = "Bottom Up"
                    # st.write(expanded_results_df.columns[expanded_results_df.columns.duplicated()])

                    # st.write(expanded_results_df.columns)


                    # if "Approach" in expanded_results_df.columns:
                    #     expanded_results_df = expanded_results_df.drop(columns=["Approach"])

                    # expanded_results_df["Approach"] = "Bottom Up"

                    # Reorder columns to make Unique_ID the first column
                    columns = ['Unique_ID'] +  [col for col in expanded_results_df.columns if col != 'Unique_ID']
                    expanded_results_df = expanded_results_df[columns]
             
                    # Drop columns with all NaN values
                    expanded_results_df = expanded_results_df.dropna(axis=1, how='all')
                    # # expanded_results_df.drop_duplicates(inplace=True)
                    # for col in expanded_results_df.columns:
                    #     if expanded_results_df[col].apply(lambda x: isinstance(x, list)).any():
                    #         st.write("List-type column:", col)

                    # expanded_results_df = expanded_results_df.applymap(
                    #     lambda x: tuple(x) if isinstance(x, list) else x
                    # )
                    # expanded_results_df = expanded_results_df.drop_duplicates()
                    # expanded_results_df = expanded_results_df.drop_duplicates()

                    # Store the expanded results in session_state
                    st.session_state["expanded_results_df"] = expanded_results_df
                    st.dataframe(st.session_state["expanded_results_df"])  # Display uploaded data

        with tab4:

            # Check if the variable is in session_state
            if "expanded_results_df" in st.session_state and st.session_state["expanded_results_df"] is not None:
                st.dataframe(st.session_state["expanded_results_df"])  # Display results
                expanded_results_df = st.session_state["expanded_results_df"]
                # expanded_results_df.drop_duplicates(inplace=True)

            else:
                uploaded_file2 = st.file_uploader("Upload the results file (CSV or Excel)", type=["csv", "xlsx"], key="file_uploader_2")

                if uploaded_file2 is not None:
                    # Read file based on its extension
                    if uploaded_file2.name.endswith(".csv"):
                        expanded_results_df = pd.read_csv(uploaded_file2)
                    else:
                        expanded_results_df = pd.read_excel(uploaded_file2)

            #         # Save to session state
            #         # expanded_results_df = expanded_results_df[expanded_results_df["Y"]=="Volume"]
            #         # st.session_state["expanded_results_df"] = expanded_results_df
                    

            #         st.success("File uploaded and stored successfully!")
            #         st.dataframe(expanded_results_df)
               

            ####################################################################################################################################################
            ####################################################################################################################################################
            ####################################################################################################################################################
            #### Y variable weights calculation (all India level)
            ####################################################################################################################################################


            # # st.write(expanded_results_df.columns[expanded_results_df.columns.duplicated()])
            # import numpy as np
            # import pandas as pd

            # def calculate_all_india_beta_weights(result_df, model_type_filter="Stacked_Generalized Constrained Ridge", intercept_name='beta0', volume_column='Volume_mean'):
            #     """
            #     Calculates All India weighted beta weights from the model results dataframe 
            #     when the volume mean is already present in the dataframe, and includes Brand level calculations.

            #     Parameters:
            #     - result_df: DataFrame containing model coefficients, Region, Brand, Volume_mean, and Model_type.
            #     - model_type_filter: Model type to filter (default: 'Stacked_Generalized Constrained Ridge').
            #     - intercept_name: Name of the intercept column (default: 'beta0').
            #     - volume_column: Name of the volume mean column (default: 'Volume_mean').

            #     Returns:
            #     - all_india_weights_df: DataFrame with All India beta weights per variable per Brand.
            #     """
            #     # Step 1: Filter model results
            #     filtered_df = result_df[result_df["Model_type"] == model_type_filter].copy()

            #     # Step 2: Identify beta columns excluding intercept
            #     beta_columns = [col for col in filtered_df.columns if col.startswith('beta_') and col != intercept_name]

            #     els_col = [col for col in filtered_df.columns if col.endswith('_elasticity')]

            #     # Step 3: Calculate sum of betas (excluding intercept) for each row
            #     filtered_df['sum_betas'] = filtered_df[beta_columns].sum(axis=1)

            #     # Step 4: Calculate beta weights within each region
            #     for col in beta_columns:
            #         filtered_df[f'{col}_weight'] = filtered_df[col] / filtered_df['sum_betas']

            #     st.write("Filtered DataFrame with beta weights:", filtered_df.head())

            #     # Step 5: Calculate weighted beta per variable across regions
            #     for col in beta_columns:
            #         filtered_df[f'{col}_weighted'] = filtered_df[f'{col}_weight'] * filtered_df[volume_column]

            #     for col in els_col:
            #         filtered_df[f"{col}_elasticity"] = filtered_df[f"{col}_elasticity"] * filtered_df[volume_column]

            #     # st.write("Filtered DataFrame with beta weights:", filtered_df[volume_column])

            #     # Step 6: Calculate All India weighted beta per variable per Brand
            #     all_india_weights = []

            #     for brand, brand_df in filtered_df.groupby('Brand'):
            #         total_volume = brand_df[volume_column].sum()
            #         for col in beta_columns:
            #             weighted_sum = brand_df[f'{col}_weighted'].sum()
            #             all_india_weight = weighted_sum / total_volume
            #             # Clean the variable name by removing the 'beta_scaled_' prefix
            #             clean_variable_name = col.replace('beta_scaled_', '')

            #             all_india_weights.append({
            #                 'Brand': brand,
            #                 'Variable': clean_variable_name,
            #                 'All_India_Weight': all_india_weight
            #             })

            #     # Step 7: Prepare final result as DataFrame
            #     all_india_weights_df = pd.DataFrame(all_india_weights)

            #     return all_india_weights_df

            
            # all_india_weights_df = calculate_all_india_beta_weights(expanded_results_df, model_type_filter="Stacked_Generalized Constrained Ridge", intercept_name='beta0', volume_column='Volume_mean')
            # st.subheader("All India Beta Weights:")
            # st.dataframe(all_india_weights_df)

            if st.checkbox("## Compute Other Variable Elasticities"):

                elasticity_rows = []
                # expanded_results_df = expanded_results_df.head(5)
                other_variables = [col.replace('beta_scaled_', '') for col in expanded_results_df.columns if col.startswith('beta_scaled_')]
                # Construct the list of other variable elasticity column names
                other_elasticity_cols = [f"{var}_elasticity" for var in other_variables]

                # Drop only these columns if they exist
                expanded_results_df = expanded_results_df.drop(
                    columns=[col for col in other_elasticity_cols if col in expanded_results_df.columns]
                )

                # st.dataframe(expanded_results_df)

                for _, row in expanded_results_df.iterrows():
                    region = row["Region"]
                    brand = row["Brand"]
                    y_var = row["Y"]
                    model_name = row["Model_type"]
                    carryover = row["Carryover"]
                    growth_rate = row["Growth_rate"]
                    mid_point = row["Mid_point"]

                    # Filter base data for this region-brand
                    df_filtered = df[(df["Region"] == region) & (df["Brand"] == brand)]
                    if df_filtered.empty:
                        continue

                    # Get row data for this model
                    region_row = row

                    # Prepare dict for elasticities
                    elasticity_dict = {}

                    for other_var in other_variables:
                        beta_scaled_col = f"beta_scaled_{other_var}"

                        # Check that both the beta and variable exist
                        if beta_scaled_col in region_row.index and other_var in df_filtered.columns:
                            try:
                                beta_scaled_val = float(region_row[beta_scaled_col])

                                # Compute min, max, range
                                var_min = df_filtered[other_var].min()
                                var_max = df_filtered[other_var].max()
                                var_range = var_max - var_min if (var_max - var_min) != 0 else None

                                # Compute means
                                mean_x = df_filtered[other_var].mean()
                                mean_y = df_filtered[y_var].mean()
                                # st.write(f"other var: {other_var}, max:{var_max}, min:{var_min}, range:{var_range}, mean_x:{mean_x}, mean_y:{mean_y}, beta_scaled_val:{beta_scaled_val}")

                                if var_range and mean_y > 0:
                                    # Reverse min-max scaling
                                    beta_unscaled = beta_scaled_val / var_range
                                    elasticity_val = beta_unscaled * (mean_x / mean_y)
                                    elasticity_dict[f"{other_var}_elasticity"] = round(elasticity_val, 4)
                                    # st.write(f"beta unscaled: {beta_unscaled}, elasticity_val: {elasticity_val}")
                                else:
                                    elasticity_dict[f"{other_var}_elasticity"] = None

                            except Exception as e:
                                st.warning(f"Error computing elasticity for {other_var} ({region}, {brand}): {e}")
                                elasticity_dict[f"{other_var}_elasticity"] = None
                        else:
                            elasticity_dict[f"{other_var}_elasticity"] = None

                    # Store the elasticity results
                    result_row = {
                        "Model_type": model_name,
                        "Y": y_var,
                        "Carryover": carryover,
                        "Growth_rate": growth_rate,
                        "Mid_point": mid_point,
                        "Region": region,
                        "Brand": brand
                    }
                    result_row.update(elasticity_dict)
                    elasticity_rows.append(result_row)

                # Combine all results
                final_elasticity_df = pd.DataFrame(elasticity_rows)
                st.dataframe(final_elasticity_df)

                # Optional: Merge with main model results
                merge_cols = ["Model_type", "Y", "Carryover", "Growth_rate", "Mid_point", "Region", "Brand"]
                merged_df = pd.merge(expanded_results_df, final_elasticity_df, on=merge_cols, how="left")
                st.dataframe(merged_df.drop_duplicates(subset=merge_cols))



            
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
                unique_regions = df["Region"].unique()

                # Extract media variables dynamically
                media_variables = [
                    col.replace('_transformed', '').replace('beta_','')
                    for col in region_weight_df.columns
                    if col.endswith('_transformed')  and col.startswith('beta_')
                ]

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

                # # Add additional media variables
                # additional_media_vars = ['TV_Total_Unique_Reach', 'Digital_Total_Unique_Reach']
                # media_variables += additional_media_vars

                # Filter data by Region and Brand
                filtered_data = {
                region: df[df["Region"] == region].copy() for region in unique_regions
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
                        beta_col = f"beta_{media_var}_transformed"
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
                            std_adstock = region_df[f"{media_var}_Adstock"].std()

                            # region_df[f"{media_var}_elasticity"] = (
                            #     beta_value
                            #     * growth_rate
                            #     * region_df[f"{media_var}_Transformed_Base"]
                            #     * (1 - region_df[f"{media_var}_Transformed_Base"])
                            #     * region_df[f"{media_var}"]
                            #     / (std_adstock * region_df["Volume"])
                            # )/(region_df[f"{media_var}_Transformed_Base"].max()-region_df[f"{media_var}_Transformed_Base"].min())

                    # Calculate contributions for other variables
                    for var in other_variables:
                        beta_col = f"beta_scaled_{var}"
                        if beta_col in region_row and f"scaled_{var}" in region_df.columns:
                            beta_value = float(region_row[beta_col])
                            region_df[f"{var}_contribution"] = beta_value * region_df[f"scaled_{var}"]
                            

                    transformed_data_list.append(region_df)

                # Concatenate all transformed data
                transformed_df = pd.concat(transformed_data_list, axis=0).reset_index(drop=True)
                return transformed_df
            

            uploaded_file3 = st.file_uploader("Upload the results file with multiple sheets (CSV or Excel)", type=["csv", "xlsx"], key="file_uploader_3")

            if uploaded_file3 is not None:
                # Case 1: CSV file — treated as single-sheet
                if uploaded_file3.name.endswith(".csv"):
                    result_df = pd.read_csv(uploaded_file3)
                    expanded_results_df = {"Default": result_df}  # Put in a dict with default key
                    st.info("CSV uploaded: treating as single-sheet with key 'Default'")

                # Case 2: Excel file — read all sheets into a dict of DataFrames
                else:
                    expanded_results_df = pd.read_excel(uploaded_file3, sheet_name=None)  # sheet_name=None loads all sheets
                    sheet_names = list(expanded_results_df.keys())
                    st.success(f"Excel uploaded with {len(sheet_names)} sheet(s): {sheet_names}")

                # Save in session state
                st.session_state["expanded_results_df"] = expanded_results_df

                # Show sample preview
                for sheet_name, brand_result_df in expanded_results_df.items():
                    st.markdown(f"### Preview: `{sheet_name}`")
                    st.dataframe(brand_result_df.head())



            # expanded_results_df = expanded_results_df[
            #     (expanded_results_df["Y"] == "Volume") &
            #     (expanded_results_df["Model_type"] == "Stacked_Generalized Constrained Ridge")
            # ]
            # expanded_results_df = expanded_results_df[expanded_results_df["Model_selected"] == 1]
            # Assuming expanded_results_df is a dict like {'BrandA': dfA, 'BrandB': dfB, ...}
            final_roi_dict = {}

            if st.checkbox("## Compute ROI and elasticity"):

                for brand_name, expanded_results_sheet in expanded_results_df.items():
                    st.markdown(f"### Processing Brand: {brand_name}")
                    expanded_results_sheet = expanded_results_sheet[
                        # (expanded_results_sheet["Y"] == "Volume") &
                        # (expanded_results_sheet["Model_type"] == "Stacked_Generalized Constrained Ridge") &
                        # (expanded_results_sheet["Region"]== "Maharashtra")
                        (expanded_results_sheet["Unique_ID"] == 1)
                    ]
                    # st.write(expanded_results_sheet)
                    
                    roi_rows = []
                    media_variables = [col.replace("beta_", "").replace("_transformed", "") 
                                    for col in expanded_results_sheet.columns 
                                    if col.startswith('beta_') and col.endswith('_transformed')]
                    # st.write(f"Media Variables: {media_variables}")
                    other_variables = [col.replace('beta_scaled_', '') for col in expanded_results_sheet.columns if col.startswith('beta_scaled_')]

                    for _, row in expanded_results_sheet.iterrows():
                        region = row["Region"]
                        model_num = row["Model_num"]
                        brand = row["Brand"]
                        y_var = row["Y"]
                        uni_id = row["Unique_ID"]
                        model_name = row["Model_type"]
                        carryover = row["Carryover"]
                        growth_rate = row["Growth_rate"]
                        mid_point = row["Mid_point"]

                        df_filtered_cont = df[(df["Region"] == region) & (df["Brand"] == brand)]
                        # st.write(df_filtered_cont)

                        filtered_model_result = pd.DataFrame([row])
                        region_row = filtered_model_result[filtered_model_result["Region"] == region].iloc[0]

                        if 'Power' in filtered_model_result.columns:
                            power = list(map(float, region_row["Power"].split(',')))
                            carryovers = list(map(float, region_row["Carryover"].split(',')))
                            uniform_power = power[0]
                            uniform_carryover = carryovers[0]
                            region_mape = region_row["Region_MAPEs"]
                            rsq = region_row["R_squared"]
                        else:
                            growth_rates = list(map(float, region_row["Growth_rate"].split(',')))
                            carryovers = list(map(float, region_row["Carryover"].split(',')))
                            mid_points = list(map(float, region_row["Mid_point"].split(',')))
                            uniform_growth_rate = growth_rates[0]
                            uniform_carryover = carryovers[0]
                            uniform_midpoint = mid_points[0]
                            region_mape = region_row["Region_MAPEs"]
                            rsq = region_row["R_squared"]

                        transformed_df = apply_transformations_with_contributions(df_filtered_cont, filtered_model_result)

                        
                        
                        # st.write(transformed_df)
                        df_roi = transformed_df.copy()
                        df_roi.columns = df_roi.columns.str.strip()

                        media_vars = {}
                        for media in media_variables:
                            contrib_col = f"{media}_contribution"
                            if "CTV" in media:
                                keyword = "CTV"
                            elif "TV" in media:
                                keyword = "TV"
                            elif "AllMedia" in media:
                                keyword = "AllMedia"
                            elif "Digital" in media:
                                keyword = "Digital"
                            else:
                                keyword = media.split('_')[0]
                            spend_col_candidates = [col for col in df_roi.columns if keyword.lower() in col.lower() and "spends" in col.lower()]
                            spend_col = spend_col_candidates[0] if spend_col_candidates else None
                            if contrib_col in df_roi.columns:
                                media_vars[media] = {
                                    "contribution": contrib_col,
                                    "spend": spend_col
                                }

                        df_roi = df_roi.sort_values("Date")
                        df_roi["Price"] = pd.to_numeric(df_roi["Price"], errors="coerce")

                        for fiscal_year, group_df in df_roi.groupby("Fiscal Year"):
                            avg_price = group_df["Price"].tail(3).mean()

                            roi_dict = {}
                            for media, cols in media_vars.items():
                                contrib_col = cols["contribution"]
                                spend_col = cols["spend"]
                                total_contribution = group_df[contrib_col].sum()

                                if spend_col and spend_col in group_df.columns:
                                    total_spend = group_df[spend_col].sum()
                                    roi = (total_contribution / total_spend) * avg_price if total_spend > 0 else None
                                else:
                                    roi = None
                                roi_dict[f"ROI_{media}"] = roi
                                # st.write(f"ROI for {media} in FY {fiscal_year}: {roi}")
                                

                            roi_row = {
                                "Model_type": model_name,
                                "Y": y_var,
                                "Carryover": carryover,
                                "Growth_rate": growth_rate,
                                "Mid_point": mid_point,
                                "Region": region,
                                "Brand": brand,
                                "Fiscal Year": fiscal_year,
                            }
                            roi_row.update(roi_dict)
                            # st.write(f"ROI Row: {roi_row}")

                            def safe_parse_list(val, default=0.0):
                                if pd.isna(val):
                                    return []
                                if isinstance(val, (list, tuple)):
                                    return list(map(float, val))
                                try:
                                    return list(map(float, str(val).split(',')))
                                except:
                                    return [default]

                            carryovers = safe_parse_list(region_row["Carryover"])
                            growth_rates = safe_parse_list(region_row["Growth_rate"])
                            mid_points = safe_parse_list(region_row["Mid_point"])

                            elasticity_dict = {}
                            
                            for media, cols in media_vars.items():
                                base_col = f"{media}_Transformed_Base"
                                adstock_col = f"{media}_Adstock"
                                media_col = f"{media}"

                                if all(col in transformed_df.columns for col in [base_col, adstock_col, y_var]):
                                    mean_base = transformed_df[base_col].mean()
                                    mean_media = transformed_df[media_col].mean()
                                    mean_adstock = transformed_df[adstock_col].mean()
                                    std_adstock = transformed_df[adstock_col].std()
                                    mean_volume = transformed_df[y_var].mean()
                                    max_val = transformed_df[base_col].max()
                                    min_val = transformed_df[base_col].min()

                                    beta_col = f"beta_{media}_transformed"
                                    beta_value = region_row.get(beta_col) or region_row.get(f"beta_{media}")

                                    media_index = media_variables.index(media)
                                    media_carryover = carryovers[media_index] if media_index < len(carryovers) else 0
                                    media_growth_rate = growth_rates[media_index] if media_index < len(growth_rates) else 1

                                    if pd.notna(beta_value) and std_adstock > 0 and mean_volume > 0:
                                        elasticity = (
                                            beta_value
                                            * (1/(max_val - min_val))
                                            * (media_growth_rate * (mean_base * (1 - mean_base)))
                                            * (1/std_adstock)
                                            * (1/(1 - media_carryover))
                                            * (mean_media/mean_volume)
                                        )
                                        elasticity_dict[f"{media}_elasticity"] = round(elasticity, 4)
                                    else:
                                        elasticity_dict[f"{media}_elasticity"] = None
                                else:
                                    elasticity_dict[f"{media}_elasticity"] = None
                                # st.write(f"Elasticity for {media} in FY {fiscal_year}: {elasticity_dict[f'{media}_elasticity']}")

                            roi_row.update(elasticity_dict)
                            roi_rows.append(roi_row)
                            # st.write(f"ROI Row with Elasticity: {roi_row}")

                    final_roi_df = pd.DataFrame(roi_rows).drop_duplicates()
                    final_roi_df["FY_numeric"] = final_roi_df["Fiscal Year"].str.extract(r"FY(\d+)").astype(int)
                    most_recent_fy = final_roi_df["FY_numeric"].max()
                    recent_roi_df = final_roi_df[final_roi_df["FY_numeric"] == most_recent_fy].drop(columns=["FY_numeric"])
                    
                    merge_cols = ["Model_type", "Y", "Carryover", "Growth_rate", "Mid_point", "Region", "Brand"]
                    merged_df = pd.merge(expanded_results_sheet, recent_roi_df, on=merge_cols, how="left")
                    merged_df = merged_df.drop_duplicates(subset=merge_cols)

                    st.dataframe(merged_df)
                    final_roi_dict[brand_name] = merged_df

                st.session_state["merged_roi_sheets"] = final_roi_dict

            from io import BytesIO

            # Create a BytesIO buffer to hold the Excel content in memory
            output = BytesIO()

            # Write to the buffer using ExcelWriter
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                for brand, brand_result_df in final_roi_dict.items():
                    brand_result_df.to_excel(writer, sheet_name=brand[:31], index=False)  # sheet_name max length = 31 chars

            # Move to beginning of the stream
            output.seek(0)

            # Add download button
            st.download_button(
                label="📥 Download ROI & Elasticity Excel",
                data=output,
                file_name="roi_elasticity_output.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )


        
            # if st.checkbox("## Compute ROI and elasticity"):

            #     # Prepare list to collect ROI results per region-brand
            #     roi_rows = []
                
            #     for _, row in expanded_results_df.iterrows():
            #             region = row["Region"]
            #             model_num = row["Model_num"]
            #             brand = row["Brand"]
            #             y_var = row["Y"]
            #             uni_id = row["Unique_ID"]
            #             model_name = row["Model_type"]
            #             carryover = row["Carryover"]
            #             growth_rate = row["Growth_rate"] # Use .get() to avoid KeyError
            #             mid_point = row["Mid_point"]
                       
            #             df_filtered_cont = df[(df["Region"] == region) & (df["Brand"] == brand)]  # Filter df for the current region

            #             filtered_model_result = pd.DataFrame([row])  # Convert row to DataFrame to keep row structure
            #             # print(filtered_model_result)

            #             region_row = filtered_model_result[filtered_model_result["Region"] == region].iloc[0]

            #             if 'Power' in filtered_model_result.columns:
            #                 # Parse parameters into lists
            #                 power = list(map(float, region_row["Power"].split(',')))
            #                 carryovers = list(map(float, region_row["Carryover"].split(',')))
            #                 # Use uniform parameters for all media variables
            #                 uniform_power = power[0]
            #                 uniform_carryover = carryovers[0]

            #                 region_mape = region_row["Region_MAPEs"]
            #                 rsq = region_row["R_squared"]

            #                 # st.write(f"#### Power: {uniform_power}, Carryover: {uniform_carryover}, Model MAPE: {region_mape:.2%}, R_sq: {rsq:.2}")
            #             else:
            #                 # Parse parameters into lists
            #                 growth_rates = list(map(float, region_row["Growth_rate"].split(',')))
            #                 carryovers = list(map(float, region_row["Carryover"].split(',')))
            #                 mid_points = list(map(float, region_row["Mid_point"].split(',')))
            #                 # Use uniform parameters for all media variables
            #                 uniform_growth_rate = growth_rates[0]
            #                 uniform_carryover = carryovers[0]
            #                 uniform_midpoint = mid_points[0]

            #                 region_mape = region_row["Region_MAPEs"]
            #                 rsq = region_row["R_squared"]

            #                 # st.write(f"#### Growth rate: {uniform_growth_rate}, Carryover: {uniform_carryover}, Model MAPE: {region_mape:.2%}, R_sq: {rsq:.2}")
                        
            #             # expanded_region_df
            #             transformed_df = apply_transformations_with_contributions(df_filtered_cont, filtered_model_result)
            #             # st.write(transformed_df)
            #             # Make a copy of the dataframe to avoid modifying original
            #             df_roi = transformed_df.copy()
            #             # st.write(media_variables)

            #             df_roi.columns = df_roi.columns.str.strip()
            #             # st.write(df_roi.columns)
            #             # st.write(f"#### Media variables: {media_variables}, Carryover: {carryover}, Growth Rate: {growth_rate}, Mid Point: {mid_point}")

            #             media_vars = {}
            #             # roi_media_variables = ["TV_Reach","Digital_Reach"]

            #             for media in media_variables:
            #                 contrib_col = f"{media}_contribution"
            #                 # st.write(contrib_col)

            #                 # Check CTV first, then TV, to avoid incorrect matching
            #                 if "CTV" in media:
            #                     keyword = "CTV"
            #                 elif "TV" in media:
            #                     keyword = "TV"
            #                 elif "AllMedia" in media:
            #                     keyword = "AllMedia"
            #                 elif "Digital" in media:
            #                     keyword = "Digital"
            #                 else:
            #                     keyword = media.split('_')[0]

            #                 # Now look for a spend column containing this keyword
            #                 spend_col_candidates = [col for col in df_roi.columns if keyword.lower() in col.lower() and "spends" in col.lower()]
            #                 spend_col = spend_col_candidates[0] if spend_col_candidates else None
            #                 # st.write(spend_col)

            #                 if contrib_col in df_roi.columns:
            #                     media_vars[media] = {
            #                         "contribution": contrib_col,
            #                         "spend": spend_col
            #                     }
            #             # st.write(media_vars)

            #             df_roi = df_roi.sort_values("Date")
            #             df_roi["Price"] = pd.to_numeric(df_roi["Price"], errors="coerce")

                        

            #             # Group by Fiscal Year
            #             for fiscal_year, group_df in df_roi.groupby("Fiscal Year"):
            #                 avg_price = group_df["Price"].tail(3).mean()
            #                 # st.write(avg_price)

            #                 roi_dict = {}
            #                 for media, cols in media_vars.items():
            #                     contrib_col = cols["contribution"]
            #                     spend_col = cols["spend"]

            #                     total_contribution = group_df[contrib_col].sum()
            #                     # st.write(total_contribution)
            #                     # st.write(avg_price)

            #                     if spend_col and spend_col in group_df.columns:
            #                         total_spend = group_df[spend_col].sum()
            #                         # st.write(f"Total Spend for {media} in FY {fiscal_year}: {total_spend}")
            #                         roi = (total_contribution / total_spend) * avg_price if total_spend > 0 else None
            #                     else:
            #                         roi = None

            #                     roi_dict[f"ROI_{media}"] = roi

            #                 # Add region, brand, fiscal year and ROI values to row
            #                 roi_row = {
            #                     "Model_type": model_name,
            #                     "Y": y_var,
            #                     "Carryover": carryover,
            #                     "Growth_rate": growth_rate,
            #                     "Mid_point":mid_point,
            #                     "Region": region,
            #                     "Brand": brand,
            #                     "Fiscal Year": fiscal_year,
                    
            #                 }
            #                 roi_row.update(roi_dict)
                            
            #                 def safe_parse_list(val, default=0.0):
            #                     if pd.isna(val):
            #                         return []
            #                     if isinstance(val, (list, tuple)):
            #                         return list(map(float, val))
            #                     try:
            #                         return list(map(float, str(val).split(',')))
            #                     except:
            #                         return [default]

            #                 carryovers = safe_parse_list(region_row["Carryover"])
            #                 growth_rates = safe_parse_list(region_row["Growth_rate"])
            #                 mid_points = safe_parse_list(region_row["Mid_point"])

            #                 # ==== Elasticity for full period ====
            #                 elasticity_dict = {}

            #                 for media, cols in media_vars.items():
            #                     base_col = f"{media}_Transformed_Base"
            #                     adstock_col = f"{media}_Adstock"
            #                     media_col = f"{media}"

            #                     if all(col in transformed_df.columns for col in [base_col, adstock_col, y_var]):
            #                         mean_base = transformed_df[base_col].mean()
            #                         mean_media = transformed_df[media_col].mean()
            #                         mean_adstock = transformed_df[adstock_col].mean()
            #                         std_adstock = transformed_df[adstock_col].std()
            #                         mean_volume = transformed_df[y_var].mean()
            #                         max_val = transformed_df[base_col].max()
            #                         min_val = transformed_df[base_col].min()

            #                         # Get beta
            #                         beta_col = f"beta_{media}_transformed"
            #                         beta_value = region_row.get(beta_col)
            #                         if beta_value is None:
            #                             beta_col_alt = f"beta_{media}"
            #                             beta_value = region_row.get(beta_col_alt)

            #                         # Get parameters
            #                         if media in media_variables:
            #                             media_index = media_variables.index(media)
            #                             media_carryover = carryovers[media_index] if media_index < len(carryovers) else 0
            #                             media_growth_rate = growth_rates[media_index] if media_index < len(growth_rates) else 1
            #                         else:
            #                             media_carryover = 0
            #                             media_growth_rate = 1

            #                         if pd.notna(beta_value) and std_adstock > 0 and mean_volume > 0:
            #                             elasticity = (
            #                                         beta_value                             # Beta
            #                                         * (1/(max_val - min_val))              # Min max normalization
            #                                         * (media_growth_rate * (mean_base * (1 - mean_base)))  # logistic
            #                                         * (1/std_adstock)                      # Standardization
            #                                         * (1/(1 - media_carryover))            # Adstock carryover
            #                                         * (mean_media/mean_volume)
            #                                     )
                                
            #                             elasticity_dict[f"{media}_elasticity"] = round(elasticity, 4)
            #                         else:
            #                             elasticity_dict[f"{media}_elasticity"] = None
            #                     else:
            #                         elasticity_dict[f"{media}_elasticity"] = None

            #                 # ==== Append full-period elasticity to row ====
            #                 roi_row.update(elasticity_dict)
            #                 roi_rows.append(roi_row)

            #     # Final DataFrame
            #     final_roi_df = pd.DataFrame(roi_rows)
            #     final_roi_df = final_roi_df.drop_duplicates()

            #     # Display
            #     st.dataframe(final_roi_df)

            #     # Step 1: Convert 'Fiscal Year' to numeric form for comparison (e.g., FY24 -> 24)
            #     final_roi_df["FY_numeric"] = final_roi_df["Fiscal Year"].str.extract(r"FY(\d+)").astype(int)

            #     # Step 2: Find the most recent fiscal year
            #     most_recent_fy = final_roi_df["FY_numeric"].max()
            #     # st.write(most_recent_fy)

            #     # Step 3: Filter only the rows for the most recent fiscal year
            #     recent_roi_df = final_roi_df[final_roi_df["FY_numeric"] == most_recent_fy].drop(columns=["FY_numeric"])
            #     # st.dataframe(recent_roi_df)

            #     # Step 4: Define merge columns (exclude 'Fiscal Year')
            #     merge_cols = ["Model_type","Y","Carryover","Growth_rate","Mid_point","Region","Brand"]

            #     # Step 5: Merge with expanded_results_df
            #     merged_df = pd.merge(
            #         expanded_results_df,
            #         recent_roi_df,
            #         on=merge_cols,
            #         how="left"
            #     )
            #     merged_df = merged_df.drop_duplicates(subset=["Region", "Brand", "Model_type", "Y","Carryover","Growth_rate","Mid_point"])
            #     st.session_state["merged_df_roi"] = merged_df
            #     st.dataframe(st.session_state["merged_df_roi"])

            # if st.checkbox("## Calculate ROI using Elasticity"):

            #     # Define your media variables
            #     media_variables = [
            #         "TV", "Digital"#, "Radio", "OOH", "Print"  # Adjust according to your data
            #     ]

            #     # Initialize output list
            #     roi_results = []

            #     # Loop through each row in model results
            #     for _, row in expanded_results_df.iterrows():
            #         region = row["Region"]
            #         brand = row["Brand"]
            #         model_name = row["Model_type"]
            #         y_var = row["Y"]
            #         carryover = row["Carryover"]
            #         growth_rate = row["Growth_rate"]
            #         mid_point = row["Mid_point"]
            #         fiscal_year = "FY25"

            #         # Filter FY25 data from base DataFrame
            #         fy25_data = df[(df["Region"] == region) & (df["Brand"] == brand) & (df["Fiscal Year"] == fiscal_year)]

            #         if fy25_data.empty:
            #             continue

            #         # Volume and average price
            #         fy25_volume = fy25_data["Volume"].mean()
            #         avg_price = fy25_data.sort_values("Date").tail(3)["Price"].mean()

            #         # Initialize result dict for this model row
            #         result_row = {
            #             "Model_type": model_name,
            #             "Y": y_var,
            #             "Carryover": carryover,
            #             "Growth_rate": growth_rate,
            #             "Mid_point": mid_point,
            #             "Region": region,
            #             "Brand": brand,
            #             "Fiscal Year": fiscal_year,
            #             "Volume": fy25_volume,
            #             "Avg_Price": avg_price
            #         }

            #         # Loop through each media variable
            #         for media in media_variables:
            #             spend_col = f"{media}_Spends"
            #             reach_col = f"{media}_Reach"
            #             elasticity_col = f"{media}_Reach_FY25elasticity"  # Assumes elasticity columns are named like this

            #             if elasticity_col not in row or pd.isna(row[elasticity_col]):
            #                 continue  # skip if no elasticity for this media

            #             elasticity = row[elasticity_col]

            #             if spend_col not in fy25_data.columns or reach_col not in fy25_data.columns:
            #                 continue

            #             media_spend = fy25_data[spend_col].sum()
            #             media_reach = fy25_data[reach_col].sum()
            #             mean_media_reach = fy25_data[reach_col].mean()

            #             if media_reach == 0 or media_spend == 0:
            #                 continue  # avoid division by zero

            #             # CPR for 1% increase in Reach
            #             cost_per_reach = (media_spend / media_reach) 

            #             # ROI calculation
            #             roi = ((fy25_volume * (elasticity / 100)) * avg_price) / (((mean_media_reach*0.01)) * cost_per_reach )
            #             result_row[f"{media}_ROI"] = roi

            #         # Append the result row (one row per model)
            #         roi_results.append(result_row)

            #     # Convert to DataFrame
            #     roi_df = pd.DataFrame(roi_results)
            #     # # Display the results
            #     # st.write(roi_df)

            #     st.session_state["FY25_ROI_results"] = roi_df
            #     st.dataframe(st.session_state["FY25_ROI_results"])

            #     # Step 4: Define merge columns (exclude 'Fiscal Year')
            #     merge_cols = ["Model_type","Y","Carryover","Growth_rate","Mid_point","Region","Brand"]

            #     # Step 5: Merge with expanded_results_df
            #     merged_df_fy25roi = pd.merge(
            #         expanded_results_df,
            #         roi_df,
            #         on=merge_cols,
            #         how="left"
            #     )
            #     merged_df_fy25roi.drop_duplicates(subset=["Region", "Brand", "Model_type", "Y","Carryover","Growth_rate","Mid_point"])
            #     st.session_state["merged_df_fy25roi"] = merged_df_fy25roi
            #     st.dataframe(st.session_state["merged_df_fy25roi"])

                ####################################################################################################################################################
                ####################################################################################################################################################
                ####################################################################################################################################################
                #### Weighted Elasticity Calculation
                ####################################################################################################################################################

            if st.checkbox("## Calculate weighted Elasticities using MAPE Weights"):
                # st.write(other_variables,media_variables)
                def calculate_mape_weighted_elasticities(df, region_col='Region', y_col='Y', mape_col='Region_MAPEs'):
                    # Collect all elasticity columns
                    elasticity_cols = [col for col in df.columns if col.endswith('_elasticity') or col.endswith('_ROI') or col.startswith("ROI_")
                                       or col.startswith("beta_") or col == "beta0" or col == "beta0_non_scaled"]
                    # elasticity_cols = [col for col in df.columns if col.endswith('_elasticity') ]
                    # st.write( elasticity_cols)
                    media_variables = [col.replace("beta_", "").replace("_transformed", "") 
                                    for col in df.columns 
                                    if col.startswith('beta_') and col.endswith('_transformed')]
                    other_variables = [col.replace("beta_scaled_", "") for col in df.columns if col.startswith("beta_scaled_")]
                    st.write(other_variables,media_variables)
                    # st.write(media_variables)
                    brand = df["Brand"].iloc[0]
                    transformation = df["Transformation_type"].iloc[0]
                    Standardization_method = df["Standardization_method"].iloc[0]
                    
                    results = []

                    # df = df[df["Region"]=="Rajasthan"]

                    # Loop through each Region and Y combination
                    for (region, y_var), group in df.groupby([region_col, y_col]):
                        # Step 1: Copy group to filtered_df
                        # st.write(region)
                        filtered_df = group.copy()
                        # filtered_df = filtered_df[filtered_df["beta_non_scaled_Penetration"] >= 0]
                        # st.write(filtered_df)
                        
                        # Build filtering conditions for other variables (non-media)
                        other_conditions = []
                        for var in other_variables:
                            # col_name = f'{var}_elasticity'
                            # st.write(f"Checking column: {col_name}")
                            col_name = f"beta_scaled_{var}"
                            if col_name in filtered_df.columns:
                                filtered_df[col_name] = pd.to_numeric(filtered_df[col_name], errors='coerce')  # ensure numeric
                                if var == 'Price':
                                    other_conditions.append((filtered_df[col_name] <= 0) | (filtered_df[col_name].isna()))
                                else:
                                    other_conditions.append((filtered_df[col_name] >= 0) | (filtered_df[col_name].isna()))
                                    # other_conditions.append(filtered_df["beta_non_scaled_SOR Vol"] >= 0)
                                # st.write(f"Exiting column: {col_name}")
                                # st.write(f"Evaluating column: {col_name}, Non-null: {filtered_df[col_name].notna().sum()}, >= 0 count: {(filtered_df[col_name] >= 0).sum()}")

                            else:
                                # Optional: Print or log missing columns for tracking
                                st.write(f"Missing column: {col_name}")

                        # Build filtering conditions for media variables
                        media_conditions = []
                        for var in media_variables:
                            col_name = f'{var}_elasticity'
                            # col_name = f'{var}'
                            if col_name in filtered_df.columns:
                                var_lower = var.lower()
                                if 'competitor' in var_lower or 'competition' in var_lower:
                                    media_conditions.append((filtered_df[col_name] <= 0) | (filtered_df[col_name].isna()))
                                else:
                                    media_conditions.append((filtered_df[col_name] >= 0) | (filtered_df[col_name].isna()))
                                # st.write(f"Existing column: {col_name}")
                            # else:
                            #     st.write(f"Missing column: {col_name}")
                        
                
                        # st.write(other_conditions)
                        # st.write(media_conditions)
                        # ✅ Combine all conditions
                        if other_conditions:
                            other_mask = np.logical_and.reduce(other_conditions)
                        else:
                            other_mask = np.ones(len(filtered_df), dtype=bool)

                        if media_conditions:
                            media_mask = np.logical_and.reduce(media_conditions)
                        else:
                            media_mask = np.ones(len(filtered_df), dtype=bool)

                        final_mask = other_mask & media_mask

                        # ✅ Apply filtering
                        filtered_df = filtered_df[final_mask]

                        # Debugging info
                        # st.write(f"Region: {region}, Y_var: {y_var}")
                        # st.write(f"Original rows: {len(group)}, After filtering: {len(filtered_df)}")

                        # # Combine all conditions
                        # all_conditions = other_conditions + media_conditions

                        # # # Apply the combined filtering
                        # final_condition = all_conditions[0]
                        # for cond in all_conditions[1:]:
                        #     final_condition &= cond

                        # # Filter the DataFrame
                        # filtered_df = filtered_df[final_condition]
                        # st.write(f"Filtered DF of Region: {region}, Y: {y_var}: {pd.DataFrame(filtered_df)}")
                        # st.write(f"=== After Filtering: Region={region}, Y={y_var} ===")
                        # st.write(filtered_df.shape)
                        # st.dataframe(filtered_df)
                        # st.dataframe(filtered_df["Region"].unique())
                        # st.write("Checking Region:", region, "| Y:", y_var)
                        # st.write("Filtered group size:", filtered_df.shape)
                        
                        # st.write("Initial group size:", group.shape)

                        # st.write("Media conditions:", media_conditions)
                        # st.write("Other conditions:", other_conditions)


                        if filtered_df.empty:
                            continue  # Skip if no valid models

                        # Step 2: Calculate difference from minimum MAPE
                        min_mape = filtered_df[mape_col].min()
                        max_mape = filtered_df[mape_col].max()
                        avg_mape = filtered_df[mape_col].mean()
                        # st.write(f"Max Mape: {max_mape}, Min Mape: {min_mape}, Mean Mape: {avg_mape}")
                        filtered_df['MAPE_Diff'] = filtered_df[mape_col] - min_mape

                        # Step 3: Calculate MAPE Weights
                        filtered_df['Likelihood'] = np.exp(-0.5 * filtered_df['MAPE_Diff'])
                        filtered_df['Weight'] = filtered_df['Likelihood'] / filtered_df['Likelihood'].sum()

                        # Step 4: Multiply each elasticity by weight
                        weighted_elasticities = {}
                        for col in elasticity_cols:
                            filtered_df[col] = pd.to_numeric(filtered_df[col], errors='coerce')
                            weighted_elasticities[col] = (filtered_df[col] * filtered_df['Weight']).sum()
                            # st.write(weighted_elasticities[col])

                        # Step 4.1: Weighted Averages for Transformation Parameters
                        transform_param_cols = ["Carryover", "Growth_rate", "Mid_point"]
                        weighted_transforms = {}

                        def parse_float_list(val):
                            if pd.isna(val):
                                return []
                            val = str(val).replace('[', '').replace(']', '').strip()
                            if val == "":
                                return []
                            try:
                                return [float(v.strip()) for v in val.split(',') if v.strip() != ""]
                            except:
                                return []


                        # st.write("Checking columns:", filtered_df.columns.tolist())
                        # st.write("Sample values for transform columns:")
                        # for param in transform_param_cols:
                        #     st.write(param, filtered_df[param].head(5).tolist())

                        for param in transform_param_cols:
                            media_param_values = []  # <-- must be defined inside this loop, once per parameter

                            for media_index, media in enumerate(media_variables):
                                weighted_sum = 0.0
                                valid_weight_sum = 0.0  # In case of malformed data
                                for _, row in filtered_df.iterrows():
                                    try:
                                        # values = list(map(float, str(row[param]).split(',')))
                                        values = parse_float_list(row[param])
                                        # st.write(f"Parsed values for {param} in row: {values}")
                                        if media_index < len(values):  # safety check
                                            weighted_sum += values[media_index] * row['Weight']
                                            valid_weight_sum += row['Weight']
                                    except Exception as e:
                                        st.write(f"Error parsing {param} for {media} in row: {row[param]}")

                                # Final weighted average for this media-variable
                                final_value = weighted_sum / valid_weight_sum if valid_weight_sum > 0 else np.nan
                                rounded_value = round(final_value, 1) if not np.isnan(final_value) else ''
                                media_param_values.append(str(rounded_value))  # <-- collect result for this media

                            # Join the rounded values into a comma-separated string
                            weighted_transforms[param] = ",".join(media_param_values)

                        # Update final output
                        weighted_elasticities.update(weighted_transforms)
                        # st.write(weighted_elasticities)



                        # Prepare the output
                        weighted_elasticities[region_col] = region
                        weighted_elasticities["Brand"] = brand
                        weighted_elasticities[y_col] = y_var
                        weighted_elasticities["Transformation_type"] = transformation
                        weighted_elasticities["Standardization_method"] = Standardization_method

                        results.append(weighted_elasticities)
                        # st.write(results)

                    # Combine all results
                    final_df = pd.DataFrame(results)
                    # Reorder columns
                    column_order = [region_col, y_col] + [col for col in final_df.columns if col not in [region_col, y_col]]
                    final_df = final_df[column_order]
                    # st.write(final_df)

                    return final_df
                
                # Example call
                st.subheader("Weighted Elasticities:")
                # weighted_els = calculate_mape_weighted_elasticities(st.session_state["merged_df_roi"], region_col='Region', y_col='Y', mape_col='Region_MAPEs')
                # st.dataframe(expanded_results_df)
                # expanded_results_df = expanded_results_df[expanded_results_df["Y"]=="SOR Vol"]
                weighted_els = calculate_mape_weighted_elasticities(expanded_results_df, region_col='Region', y_col='Y', mape_col='Region_MAPEs')
                st.session_state["weighted_els"] = weighted_els
                st.write(st.session_state["weighted_els"])
                all_brand_results = []

                for brand in expanded_results_df["Brand"].unique():
                    st.markdown(f"### Processing Brand: {brand}")
                    
                    brand_df = expanded_results_df[expanded_results_df["Brand"] == brand]
                    
                    weighted_els = calculate_mape_weighted_elasticities(
                        brand_df,
                        region_col='Region',
                        y_col='Y',
                        mape_col='Region_MAPEs'
                    )
                    
                    all_brand_results.append(weighted_els)

                # Combine all brand-level results
                final_weighted_els = pd.concat(all_brand_results, ignore_index=True)

                # Store in session state
                st.session_state["weighted_els"] = final_weighted_els

                # Display
                st.subheader("Final Weighted Elasticities for All Brands:")
                st.dataframe(st.session_state["weighted_els"])


            ########### upload file and show MAPE and ROI for weighted volume models
            ###################################################################################################################################################

            import streamlit as st
            import pandas as pd

            # File type selection
            file_type = st.radio("Select file type", ["Excel", "CSV"])

            if file_type == "Excel":
                uploaded_file = st.file_uploader("Upload an Excel file", type=["xlsx", "xls"])
                
                if uploaded_file is not None:
                    # Load the Excel file
                    xls = pd.ExcelFile(uploaded_file)

                    # Show available sheet names
                    sheet_name = st.selectbox("Select a sheet", xls.sheet_names)

                    # Read the selected sheet
                    vol_model = pd.read_excel(xls, sheet_name=sheet_name)

                    st.write(f"✅ Loaded Excel sheet: {sheet_name}")
                    st.dataframe(vol_model)

            elif file_type == "CSV":
                uploaded_file = st.file_uploader("Upload a CSV file", type=["csv"])
                
                if uploaded_file is not None:
                    # Read CSV directly
                    vol_model = pd.read_csv(uploaded_file)

                    st.write("✅ Loaded CSV file")
                    st.dataframe(vol_model)



            if st.checkbox("Weighted Volume models MAPE and ROI"):
                weighted_els_vol = vol_model.copy()
                # weighted_els_vol = weighted_els_vol[weighted_els_vol["Y"]=="Volume"]
                
                # Example: assuming weighted_els_vol already loaded
                # Let user select Y variable
                if "Y" in weighted_els_vol.columns:
                    y_var = st.selectbox("Select Y variable", weighted_els_vol["Y"].unique())

                    # Filter based on selection
                    weighted_els_vol = weighted_els_vol[weighted_els_vol["Y"] == y_var]

                    st.write(f"✅ Filtered for Y = {y_var}")
                    st.dataframe(weighted_els_vol)
                else:
                    st.error("⚠️ Column 'Y' not found in the DataFrame.")
                # st.dataframe(weighted_els_vol)

                # Prepare list to collect ROI results per region-brand
                roi_rows = []
                
                for _, row in weighted_els_vol.iterrows():
                        region = row["Region"]
                        # model_num = row["Model_num"]
                        brand = row["Brand"]
                        y_var = row["Y"]
                        # uni_id = row["Unique_ID"]
                        # model_name = row["Model_type"]
                        carryover = row["Carryover"]
                        growth_rate = row["Growth_rate"] # Use .get() to avoid KeyError
                        mid_point = row["Mid_point"]
                        # st.write(region,brand)
                        media_variables = [col.replace("beta_", "").replace("_transformed", "") 
                                        for col in weighted_els_vol.columns 
                                        if col.startswith('beta_') and col.endswith('_transformed')]
                        
                        df_filtered_cont = df[(df["Region"] == region) & (df["Brand"] == brand)]  # Filter df for the current region
                        df_filtered_cont = df_filtered_cont.sort_values("Date")
                        # st.dataframe(df_filtered_cont.shape)

                        filtered_model_result = pd.DataFrame([row])  # Convert row to DataFrame to keep row structure
                        # st.dataframe(filtered_model_result)

                        region_row = filtered_model_result[filtered_model_result["Region"] == region].iloc[0]

                        
                        # expanded_region_df
                        transformed_df = apply_transformations_with_contributions(df_filtered_cont, filtered_model_result)
                        # st.write(transformed_df.columns)
                        import matplotlib.pyplot as plt
                        import numpy as np

                        # Calculate Prediction
                        transformed_df["beta0"] = pd.to_numeric(transformed_df["beta0"], errors="coerce")
                        contrib_cols = [col for col in transformed_df.columns if col.endswith("_contribution")]
                        transformed_df[contrib_cols] = transformed_df[contrib_cols].apply(pd.to_numeric, errors="coerce")
                        transformed_df["Prediction"] = transformed_df["beta0"] + transformed_df[contrib_cols].sum(axis=1)

                        # Ensure actuals are numeric
                        # transformed_df["Volume"] = pd.to_numeric(transformed_df["Volume"], errors="coerce")
                        if filtered_model_result["Brand"].iloc[0] == "Aer O":
                            transformed_df["Filtered_Sales_Qty_Total"] = pd.to_numeric(transformed_df["Filtered_Sales_Qty_Total"], errors="coerce")

                            # Drop NA rows for MAPE calculation
                            mape_df = transformed_df.dropna(subset=["Filtered_Sales_Qty_Total", "Prediction"])
                            mape = np.mean(np.abs((mape_df["Filtered_Sales_Qty_Total"] - mape_df["Prediction"]) / mape_df["Filtered_Sales_Qty_Total"])) if not mape_df.empty else np.nan
                            # Plot Actual vs Predicted
                            date_values = transformed_df['Date']
                        
                            actual_values = transformed_df["Filtered_Sales_Qty_Total"]
                        else:
                            transformed_df[y_var] = pd.to_numeric(transformed_df[y_var], errors="coerce")

                            # Drop NA rows for MAPE calculation
                            mape_df = transformed_df.dropna(subset=[y_var, "Prediction"])
                            mape = np.mean(np.abs((mape_df[y_var] - mape_df["Prediction"]) / mape_df[y_var])) if not mape_df.empty else np.nan
                            # Plot Actual vs Predicted
                            date_values = transformed_df['Date']
                            actual_values = transformed_df[y_var]
                        mainmedia_pred_values = transformed_df['Prediction']
                        # mediagenre_pred_values = transformed_df['Mediagenre_predY']

                        fig = go.Figure()
                        fig.add_trace(go.Scatter(x=date_values, y=actual_values, mode='lines+markers', name='Actual Volume'))
                        fig.add_trace(go.Scatter(x=date_values, y=mainmedia_pred_values, mode='lines+markers', name=f'Prediction'))
                    
                        # fig.update_layout(title=f'Actual vs Predicted Volume: {region} - {brand}',
                        #                 xaxis_title='Date',
                        #                 yaxis_title='Volume',
                        #                 legend_title='Legend')
                        # Update layout with larger fonts
                        fig.update_layout(
                            title={
                                'text': f'Actual vs Predicted {y_var}: {region} - {brand} (MAPE: {mape:.2%})',
                                'x': 0.5,  # Center the title
                                'xanchor': 'center',
                                'font': dict(size=22)  # Title font size
                            },
                            xaxis_title='Date',
                            yaxis_title=y_var,
                            legend=dict(
                                title='Legend',
                                font=dict(size=14),        # Legend font size
                                title_font=dict(size=14)   # Legend title font size
                            ),
                            xaxis=dict(title_font=dict(size=14), tickfont=dict(size=12)),
                            yaxis=dict(title_font=dict(size=14), tickfont=dict(size=12))
                        )

                        st.plotly_chart(fig, use_container_width=True, key=f"plot_{region}_{brand}_actual_vs_predicted ")

                        # st.write(transformed_df)
                        df_roi = transformed_df.copy()
                        df_roi.columns = df_roi.columns.str.strip()
                        # st.write(media_variables)

                        media_vars = {}
                        for media in media_variables:
                            contrib_col = f"{media}_contribution"
                            if "CTV" in media:
                                keyword = "CTV"
                            elif "TV" in media:
                                keyword = "TV"
                            elif "AllMedia" in media:
                                keyword = "AllMedia"
                            elif "Digital" in media:
                                keyword = "Digital"
                            else:
                                keyword = media.split('_')[0]
                            spend_col_candidates = [col for col in df_roi.columns if keyword.lower() in col.lower() and "spends" in col.lower()]
                            spend_col = spend_col_candidates[0] if spend_col_candidates else None
                            if contrib_col in df_roi.columns:
                                media_vars[media] = {
                                    "contribution": contrib_col,
                                    "spend": spend_col
                                }

                        df_roi = df_roi.sort_values("Date")
                        df_roi["Price"] = pd.to_numeric(df_roi["Price"], errors="coerce")
                        # st.write(df_roi["Price"])

                        for fiscal_year, group_df in df_roi.groupby("Fiscal Year"):
                            avg_price = group_df["Price"].tail(3).mean()

                            roi_dict = {}
                            for media, cols in media_vars.items():
                                contrib_col = cols["contribution"]
                                spend_col = cols["spend"]
                                total_contribution = group_df[contrib_col].sum()


                                if spend_col and spend_col in group_df.columns:
                                    total_spend = group_df[spend_col].sum()
                                    # st.write(avg_price)
                                    roi = (total_contribution / total_spend) * avg_price if total_spend > 0 else None
                                else:
                                    roi = None
                                roi_dict[f"ROI_weighted_{media}"] = roi
                                # st.write(f"ROI for {media} in FY {fiscal_year}: {roi}")
                                

                            roi_row = {
                                # "Model_type": model_name,
                                "Y": y_var,
                                "MAPE": mape,
                                "Carryover": carryover,
                                "Growth_rate": growth_rate,
                                "Mid_point": mid_point,
                                "Region": region,
                                "Brand": brand,
                                "Fiscal Year": fiscal_year,
                            }
                            roi_row.update(roi_dict)
                            # st.write(f"ROI Row: {roi_row}")

                            def safe_parse_list(val, default=0.0):
                                if pd.isna(val):
                                    return []
                                if isinstance(val, (list, tuple)):
                                    return list(map(float, val))
                                try:
                                    return list(map(float, str(val).split(',')))
                                except:
                                    return [default]

                            carryovers = safe_parse_list(region_row["Carryover"])
                            growth_rates = safe_parse_list(region_row["Growth_rate"])
                            mid_points = safe_parse_list(region_row["Mid_point"])

                            elasticity_dict = {}
                            for media, cols in media_vars.items():
                                base_col = f"{media}_Transformed_Base"
                                adstock_col = f"{media}_Adstock"
                                media_col = f"{media}"

                                if all(col in transformed_df.columns for col in [base_col, adstock_col, y_var]):
                                    mean_base = transformed_df[base_col].mean()
                                    mean_media = transformed_df[media_col].mean()
                                    mean_adstock = transformed_df[adstock_col].mean()
                                    std_adstock = transformed_df[adstock_col].std()
                                    mean_volume = transformed_df[y_var].mean()
                                    max_val = transformed_df[base_col].max()
                                    min_val = transformed_df[base_col].min()

                                    beta_col = f"beta_{media}_transformed"
                                    beta_value = region_row.get(beta_col) or region_row.get(f"beta_{media}")

                                    media_index = media_variables.index(media)
                                    media_carryover = carryovers[media_index] if media_index < len(carryovers) else 0
                                    media_growth_rate = growth_rates[media_index] if media_index < len(growth_rates) else 1

                                    if pd.notna(beta_value) and std_adstock > 0 and mean_volume > 0:
                                        elasticity = (
                                            beta_value
                                            * (1/(max_val - min_val))
                                            * (media_growth_rate * (mean_base * (1 - mean_base)))
                                            * (1/std_adstock)
                                            * (1/(1 - media_carryover))
                                            * (mean_media/mean_volume)
                                        )
                                        elasticity_dict[f"{media}_weighted_elasticity"] = round(elasticity, 4)
                                    else:
                                        elasticity_dict[f"{media}_weighted_elasticity"] = None
                                else:
                                    elasticity_dict[f"{media}_weighted_elasticity"] = None
                                # st.write(f"Elasticity for {media} in FY {fiscal_year}: {elasticity_dict[f'{media}_elasticity']}")

                            roi_row.update(elasticity_dict)
                            roi_rows.append(roi_row)
                            # st.write(f"ROI Row with Elasticity: {roi_row}")

                final_roi_df = pd.DataFrame(roi_rows).drop_duplicates()
                # st.dataframe(final_roi_df)
                final_roi_df["FY_numeric"] = final_roi_df["Fiscal Year"].str.extract(r"FY(\d+)").astype(int)
                most_recent_fy = final_roi_df["FY_numeric"].max()
                recent_roi_df = final_roi_df[final_roi_df["FY_numeric"] == most_recent_fy].drop(columns=["FY_numeric"])
                
                merge_cols = ["Y", "Carryover", "Growth_rate", "Mid_point", "Region", "Brand"]
                merged_df = pd.merge(weighted_els_vol, recent_roi_df, on=merge_cols, how="left")
                merged_df = merged_df.drop_duplicates(subset=merge_cols)

                st.dataframe(merged_df)








        with tab2:
            st.write("### Top Down Model")

            # # # Page title
            # # st.title("Modeling Options")
            # with st.expander("#### Modeling Options", expanded=False):

            #     # Auto-load selections from Bottom-Up Model
            #     auto_selections = st.session_state["selections"]
            #     # st.write(auto_selections)

            #     col1, col2, col3 = st.columns(3)
            #     # Extract unique values for dynamic dropdowns
            #     available_regions = df["Region"].unique().tolist()
            #     available_markets = df["Market"].unique().tolist()
            #     available_brands = df["Brand"].unique().tolist()

            #     with col1:
            #         # Region selection
            #         regions = st.multiselect("Select Regions", available_regions, default=auto_selections.get("regions", []), key="Top down1")

            #     with col2:
            #         # Market selection
            #         markets = st.multiselect("Select Markets", available_markets, default=auto_selections.get("markets", []), key="Top down2")

            #     with col3:
            #         # Brand selection
            #         brands = st.multiselect("Select Brands", available_brands, default=auto_selections.get("brands", []), key="Top down3")

            #     col4, col5, col6, col7 = st.columns(4)

            #     with col4:
            #         # Dependent variable selection
            #         y_variables = st.multiselect("Select Dependent Variable (y)", df.columns.tolist(), default=auto_selections.get("y_variables", []), key="Top down4")  #, default=["Filtered Volume Index"]

            #     with col5:
            #         # Media variables selection
            #         main_media_variables = st.multiselect(
            #             "Select Main Media Variables", df.columns.tolist(), key="Top down5"
            #         # default=['Digital_Total_Unique_Reach', 'TV_Total_Unique_Reach']
            #         )

            #     with col6:
            #         # Other variables selection
            #         other_variables = st.multiselect(
            #             "Select Other Variables", df.columns.tolist(), default=auto_selections.get("other_variables", []), key="Top down6"
            #             #default=['D1', 'Price', 'A&P_Amount_Spent', 'Region_Brand_seasonality']
            #         )

            #     with col7:
            #         non_scaled_variables = st.multiselect(
            #             "Select Other Non Scaled Variables", df.columns.tolist(), 
            #             default=auto_selections.get("non_scaled_variables", []), key="Top down7"
            #         )


            #     import streamlit as st

            #     # # Function to parse user input
            #     # def parse_input(input_text):
            #     #     # Convert list to string if needed
            #     #     if isinstance(input_text, list):
            #     #         input_text = ",".join(map(str, input_text))  # Join list elements into a string
            #     #     try:
            #     #         return [float(x.strip()) for x in input_text.split(",") if x.strip()]
            #     #     except ValueError:
            #     #         return []
            #     def parse_input(input_str, default_values):
            #         """Parse comma-separated input with validation and fallback to defaults"""
            #         try:
            #             # Convert default_values to list of floats if it's a string
            #             if isinstance(default_values, str):
            #                 default_values = [float(x.strip()) for x in default_values.split(",") if x.strip()]
            #             elif isinstance(default_values, (int, float)):
            #                 default_values = [float(default_values)]
            #             elif not isinstance(default_values, list):
            #                 default_values = []
                        
            #             # Ensure input is a string
            #             if isinstance(input_str, (list, tuple)):
            #                 input_str = ",".join(str(x) for x in input_str)
            #             elif not isinstance(input_str, str):
            #                 input_str = str(input_str)
                            
            #             # Handle empty input
            #             if not input_str.strip():
            #                 return default_values
                            
            #             # Parse comma-separated values
            #             parsed_values = []
            #             for x in input_str.split(","):
            #                 x = x.strip()
            #                 if x:  # Only process non-empty strings
            #                     try:
            #                         parsed_values.append(float(x))
            #                     except ValueError:
            #                         continue  # Skip invalid numbers
                                
            #             return parsed_values if parsed_values else default_values
            #         except Exception:
            #             return default_values
            #                     # col8, col9, col10 = st.columns(3)

            #     # with col8:
            #     #     # Transformation type selection (first, because later inputs depend on it)
            #     #     transformation_type = st.selectbox(
            #     #         "Select Transformation Type", 
            #     #         ["logistic", "power"], 
            #     #         index=0, 
            #     #         key="transformation_type"
            #     #     )

            #     #     if transformation_type == "logistic":
            #     #     #     # User input for Growth Rate
            #     #     #     growth_input = st.text_area("Enter Growth Rates (comma-separated)", "3.5", key="Bottom up11")
            #     #     #     growth_rates = parse_input(growth_input)
            #     #     # else:
            #     #     #     growth_rates = []  # or None
            #     #         # User input for Growth Rate with validation
            #     #         growth_input = st.text_area(
            #     #             "Enter Growth Rates (comma-separated)", 
            #     #             value="3.5",
            #     #             help="Enter comma-separated values like '3.5' or '3.5,4.0'",
            #     #             key="Bottom up11"
            #     #         )
            #     #         growth_rates = parse_input(growth_input, [3.5])
            #     #     else:
            #     #         growth_rates = []

            #     #     # Model types selection
            #     #     model_types = st.multiselect(
            #     #         "Select Model Types", 
            #     #         ["Generalized Constrained Ridge", "Ridge", "Linear Regression", "Lasso", "Elastic Net"], 
            #     #         default=["Generalized Constrained Ridge"], 
            #     #         key="Bottom up8"
            #     #     )

            #     # with col9:
            #     #     # # User input for Carryover Rate (always needed)
            #     #     # carryover_input = st.text_area("Enter Carryover Rates (comma-separated)", "0.8", key="Bottom up12")
            #     #     # carryover_rates = parse_input(carryover_input)
            #     #     # User input for Carryover Rate with validation
            #     #     carryover_input = st.text_area(
            #     #         "Enter Carryover Rates (comma-separated)", 
            #     #         value="0.8",
            #     #         help="Enter comma-separated values like '0.8' or '0.8,0.6'",
            #     #         key="Bottom up12"
            #     #     )
            #     #     carryover_rates = parse_input(carryover_input, [0.8])

            #     #     # Standardization method selection
            #     #     standardization_method = st.selectbox(
            #     #         "Select Standardization Method", 
            #     #         ['minmax', 'zscore', 'none'], 
            #     #         index=0, 
            #     #         key="Bottom up9"
            #     #     )

            #     # with col10:
            #     #     if transformation_type == "logistic":
            #     #     #     # User input for Midpoints
            #     #     #     midpoint_input = st.text_area("Enter Midpoints (comma-separated)", "0", key="Bottom up13")
            #     #     #     midpoints = parse_input(midpoint_input)
            #     #     #     powers = []  # Empty, not needed
            #     #     # else:
            #     #     #     # User input for Powers
            #     #     #     power_input = st.text_area("Enter Powers (comma-separated)", "0.5", key="Bottom up14")
            #     #     #     powers = parse_input(power_input)
            #     #     #     midpoints = []  # Empty, not needed
            #     #         # User input for Midpoints with validation
            #     #         midpoint_input = st.text_area(
            #     #             "Enter Midpoints (comma-separated)", 
            #     #             value="0",
            #     #             help="Enter comma-separated values like '0' or '0,0.5'",
            #     #             key="Bottom up13"
            #     #         )
            #     #         midpoints = parse_input(midpoint_input, [0])
            #     #         powers = []
            #     #     else:
            #     #         # User input for Powers with validation
            #     #         power_input = st.text_area(
            #     #             "Enter Powers (comma-separated)", 
            #     #             value="0.5",
            #     #             help="Enter comma-separated values like '0.5' or '0.5,1.0'",
            #     #             key="Bottom up14"
            #     #         )
            #     #         powers = parse_input(power_input, [0.5])
            #     #         midpoints = []

            #     #     # Option to apply same parameters across all media variables
            #     #     apply_same_params = st.selectbox(
            #     #         "Apply same parameters across all media variables", 
            #     #         ["Yes", "No"], 
            #     #         index=0, 
            #     #         key="apply_params_media"
            #     #     )
                    
            #     col8, col9, col10 = st.columns(3)

            #     with col8:
            #         # Transformation type selection (first, because later inputs depend on it)
            #         transformation_type = st.selectbox(
            #             "Select Transformation Type", 
            #             ["logistic", "power"], 
            #             index=0 if auto_selections.get("transformation_type", "logistic") == "logistic" else 1
            #             # key="transformation_type"
            #         )

            #         if transformation_type == "logistic":
            #             # User input for Growth Rate
            #             growth_input = st.text_area("Enter Growth Rates (comma-separated)", value = str(auto_selections.get("growth_rates", "3.5")), key="Top down11")
            #             growth_rates = parse_input(growth_input,auto_selections.get("growth_rates", [3.5]))
            #         # else:
            #             # growth_rates = []  # or None

            #         # Model types selection
            #         model_types = st.multiselect(
            #             "Select Model Types", 
            #             ["Generalized Constrained Ridge", "Ridge", "Linear Regression", "Lasso", "Elastic Net"], 
            #             default=auto_selections.get("model_types", ["Generalized Constrained Ridge"]), key="Top down8"
            #         )

            #     with col9:
            #         # User input for Carryover Rate (always needed)
            #         carryover_input = st.text_area("Enter Carryover Rates (comma-separated)", value = str(auto_selections.get("carryover_rates", "0.8")), key="Top down12")
            #         carryover_rates = parse_input(carryover_input,auto_selections.get("carryover_rates", [0.8]))

            #         # Standardization method selection
            #         standardization_method = st.selectbox(
            #             "Select Standardization Method", 
            #             ['minmax', 'zscore', 'none'], 
            #             # index=0, 
            #             index=0 if auto_selections.get('Standardization_method', 'minmax') == "minmax" 
            #             else 1 if auto_selections.get('Standardization_method', 'minmax') == "zscore" 
            #             else 2
            #         )

            #     with col10:
            #         if transformation_type == "logistic":
            #             # User input for Midpoints
            #             midpoint_input = st.text_area("Enter Midpoints (comma-separated)", value = str(auto_selections.get("midpoints", "0")), key="Top down13")
            #             midpoints = parse_input(midpoint_input, auto_selections.get("midpoints", [0]))
            #             # powers = []  # Empty, not needed
            #         else:
            #             # User input for Powers
            #             power_input = st.text_area("Enter Powers (comma-separated)", value = str(auto_selections.get("powers","0.5")), key="Top down14")
            #             powers = parse_input(power_input, auto_selections.get("powers",[0.5]))
            #             # midpoints = []  # Empty, not needed

            #         # Option to apply same parameters across all media variables
            #         apply_same_params = st.selectbox(
            #             "Apply same parameters across all media variables", 
            #             ["Yes", "No"], 
            #             # index=0, 
            #             index=0 if auto_selections.get("apply_same_params", "Yes") == "Yes" else 1
            #         )



            # # Run modeling button
            # if st.button("Run Model"):
            #     st.write("Running model with the selected options...")
                
            #     # # Call the modeling function with selected parameters
            #     # TD_results_df = generalized_modeling_recursive(
            #     #     df=df,
            #     #     Region=regions,
            #     #     Market=markets,
            #     #     Brand=brands,
            #     #     y_variables=y_variables,
            #     #     media_variables=main_media_variables,
            #     #     other_variables=other_variables,
            #     #     non_scaled_variables = non_scaled_variables,
            #     #     growth_rates=growth_rates,
            #     #     carryover_rates=carryover_rates,
            #     #     midpoints=midpoints,
            #     #     model_types=model_types,
            #     #     standardization_method=standardization_method,
            #     #     apply_same_params=apply_same_params
            #     # )

            #     # Call the modeling function with selected parameters
            #     TD_results_df = generalized_modeling_recursive(
            #         df=df,
            #         Region=regions,
            #         Market=markets,
            #         Brand=brands,
            #         y_variables=y_variables,
            #         media_variables=main_media_variables,
            #         other_variables=other_variables,
            #         non_scaled_variables = non_scaled_variables,
            #         growth_rates=growth_rates,
            #         carryover_rates=carryover_rates,
            #         midpoints=midpoints,
            #         model_types=model_types,
            #         standardization_method=standardization_method,
            #         apply_same_params=apply_same_params,
            #         transformation_type=transformation_type,
            #         powers=powers
            #     )
                
            #     st.write("Modeling completed!")
            #     st.dataframe(TD_results_df)  # Display results

            #     # Store results_df in session_state
            #     st.session_state["TD_results_df"] = TD_results_df
            # # st.dataframe(results_df)  # Display results
            # # else:
            # #     st.warning("Please upload a CSV file to proceed.")

            # if "expanded_TD_results_df" not in st.session_state:
            #     st.session_state["expanded_TD_results_df"] = None  # or pd.DataFrame() if applicable

            # if st.button("Final TD_results_df"):
            #     if "TD_results_df" not in st.session_state:
            #         st.warning("Please run the model first by clicking 'Run Model'.")
            #     else:
            #         TD_results_df = st.session_state["TD_results_df"]  # Retrieve stored results

            #         expanded_results = []

            #         # Loop through each model in the results dataframe
            #         for _, model_row in TD_results_df.iterrows():
            #             # Extract model type and Region
            #             model_type = model_row['Model_type']
            #             original_region = model_row.get('Region', None)  # Get the original region from the results dataframe

            #             # Determine if the model is stacked
            #             is_stacked = model_type.startswith("Stacked")

            #             # Extract feature names and parameters dynamically
            #             feature_names = [
            #                 col.split('beta_')[1] for col in model_row.keys() if col.startswith('beta_')
            #             ]
            #             model = {
            #                 "b": model_row['beta0'],
            #                 "W": np.array([model_row[f'beta_{col}'] for col in feature_names]),
            #             }

            #             # Handle stacked models
            #             if is_stacked:
            #                 # Extract regions dynamically
            #                 Region = [col.split('Region_')[1] for col in feature_names if col.startswith('Region_')]

            #                 # Parse Region_MAPEs into a dictionary
            #                 region_mapes = {
            #                     region_mape.split(':')[0]: float(region_mape.split(':')[1])
            #                     for region_mape in model_row['Region_MAPEs'].split(',')
            #                 }

            #                 region_y_means = {
            #                     region_y_mean.split(':')[0]: float(region_y_mean.split(':')[1])
            #                     for region_y_mean in model_row['Region_Y_means'].split(',')
            #                 }

            #                 # # Extract means of variables for each region from the results_df
            #                 # variable_means = {
            #                 #     var: {
            #                 #         region_mean.split(':')[0]: float(region_mean.split(':')[1])
            #                 #         for region_mean in model_row[f"{var}_mean"].split(',')
            #                 #     }
            #                 #     for var in feature_names if f"{var}_mean" in model_row
            #                 # }
            #                 # Extract means of variables for all regions from the results_df
            #                 # variable_means = {}
            #                 # for col in model_row.keys():
            #                 #     if col.endswith("_mean"):
            #                 #         variable_name = col.replace("_mean", "")
            #                 #         variable_means[variable_name] = {
            #                 #             region_mean.split(':')[0]: float(region_mean.split(':')[1])
            #                 #             for region_mean in model_row[col].split(',')
            #                 #         }
            #                 variable_means = {}
            #                 for col in model_row.keys():
            #                     if col.endswith("_mean"):
            #                         variable_name = col.replace("_mean", "")
            #                         col_value = model_row[col]
                                    
            #                         if isinstance(col_value, str):
            #                             variable_means[variable_name] = {
            #                                 region_mean.split(':')[0]: float(region_mean.split(':')[1])
            #                                 for region_mean in col_value.split(',')
            #                             }
            #                         else:
            #                             # Optional: handle non-string case, e.g., float directly assigned to a default region
            #                             variable_means[variable_name] = {"default": float(col_value)}
            #                 # print("variable_means :", variable_means)

            #                 # Loop through each region
            #                 for region in Region:
            #                     # Extract base intercept and region-specific intercept
            #                     base_intercept = model["b"]
            #                     region_intercept = (
            #                         model["W"][feature_names.index(f"Region_{region}")] if f"Region_{region}" in feature_names else 0
            #                     )
            #                     adjusted_intercept = base_intercept + region_intercept

            #                     # Calculate adjusted betas
            #                     adjusted_betas = {}
            #                     for var in feature_names:
            #                         # Skip interaction terms (variables starting with {region}_interaction_)
            #                         if not var.startswith("Region_") and not any(var.startswith(f"{region}_interaction") for region in Region):
            #                             # Base coefficient for the variable
            #                             base_beta = model["W"][feature_names.index(var)]

            #                             # Interaction term adjustment (if exists)
            #                             interaction_term = f"{region}_interaction_{var}"
            #                             interaction_beta = (
            #                                 model["W"][feature_names.index(interaction_term)]
            #                                 if interaction_term in feature_names else 0
            #                             )

            #                             # Store adjusted beta
            #                             adjusted_betas[var] = base_beta + interaction_beta

            #                     # # Prepare a dictionary for the region-specific row
            #                     # region_row = {
            #                     #     'Model_num': model_row['Model_num'],
            #                     #     'Model_type': model_type,
            #                     #     'Market': model_row['Market'],
            #                     #     'Brand': model_row['Brand'],
            #                     #     'Region': region,
            #                     #     'Model_selected': model_row['Model_selected'],
            #                     #     'MAPE': model_row['MAPE'],
            #                     #     'Region_MAPEs': region_mapes.get(region, None),  # Assign region-specific MAPE
            #                     #     'R_squared': model_row['R_squared'],
            #                     #     'Adjusted_R_squared': model_row['Adjusted_R_squared'],
            #                     #     'AIC': model_row['AIC'],
            #                     #     'BIC': model_row['BIC'],
            #                     #     'Y': model_row['Y'],
            #                     #     'beta0': adjusted_intercept,
            #                     #     **{
            #                     #         f'beta_{var}': adjusted_betas[var]
            #                     #         for var in adjusted_betas.keys()
            #                     #     },  # Add region-specific means for each variable
            #                     #     'Growth_rate': model_row['Growth_rate'],
            #                     #     'Mid_point': model_row['Mid_point'],
            #                     #     'Carryover': model_row['Carryover'],
            #                     #     'Standardization_method': model_row['Standardization_method'],
            #                     # }

            #                     # # Append the region-specific row to the expanded results
            #                     # expanded_results.append(region_row)
            #                                             # Prepare the variable-specific mean strings for this region
            #                     region_variable_means = {
            #                         f"{var}_mean": f"{region}:{means.get(region, 0)}"
            #                         for var, means in variable_means.items()
            #                     }
            #                     # Build the expanded result dict
            #                     region_row = {
            #                         'Model_num': model_row['Model_num'],
            #                         'Model_type': model_row['Model_type'],
            #                         'Market': model_row['Market'],
            #                         'Brand': model_row['Brand'],
            #                         'Region': region,
            #                         'Model_selected': model_row['Model_selected'],
            #                         'MAPE': model_row['MAPE'],
            #                         'Avg_MAPE': model_row['Avg_MAPE'],
            #                         "Region_MAPEs": region_mapes.get(region, None),
            #                         'R_squared': model_row['R_squared'],
            #                         'Adjusted_R_squared': model_row['Adjusted_R_squared'],
            #                         'AIC': model_row['AIC'],
            #                         'BIC': model_row['BIC'],
            #                         'Y': model_row['Y'],
            #                         'Region_Y_means': model_row['Region_Y_means'],
            #                         'beta0': adjusted_intercept,
            #                         **{f'beta_{var}': adjusted_betas[var] for var in adjusted_betas.keys()},
            #                         **region_variable_means,
            #                         'Transformation_type': model_row.get('Transformation_type', "logistic"),   # default logistic
            #                         'Transformation_params': model_row.get('Transformation_params', ""),  # safe default
            #                         'Standardization_method': model_row.get('Standardization_method', 'minmax')
            #                     }

            #                     # Add Transformation-specific columns
            #                     if model_row.get('Transformation_type') == "logistic":
            #                         region_row.update({
            #                             'Growth_rate': model_row.get('Growth_rate', ''),
            #                             'Carryover': model_row.get('Carryover', ''),
            #                             'Mid_point': model_row.get('Mid_point', '')
            #                         })
            #                     elif model_row.get('Transformation_type') == "power":
            #                         region_row.update({
            #                             'Carryover': model_row.get('Carryover', ''),
            #                             'Power': model_row.get('Power', '')
            #                         })

            #                     # Append the region-specific row
            #                     expanded_results.append(region_row)
            #             else:
            #                 # For non-stacked models, retain the original row
            #                 region_row = model_row.to_dict()  # Convert the row to a dictionary
                        
                            
            #                 expanded_results.append(region_row)

            #         # Replace the original results with the expanded results
            #         # Add a unique identifier to each row
            #         expanded_TD_results_df = pd.DataFrame(expanded_results)  # Convert to DataFrame for further use
            #         # Replace None values in 'Region_MAPEs' with the corresponding 'MAPE' values
            #         expanded_TD_results_df['Region_MAPEs'] = expanded_TD_results_df.apply(
            #             lambda row: row['MAPE'] if pd.isna(row['Region_MAPEs']) or row['Region_MAPEs'] in ["None", "nan", ""] else row['Region_MAPEs'],
            #             axis=1
            #         )
            #         import re

            #         # Make sure 'None' values are actual NaNs
            #         expanded_TD_results_df['Region_Y_means'] = expanded_TD_results_df['Region_Y_means'].replace('None', np.nan)

            #         # # Check types
            #         # st.write(expanded_results_df['Brand'].apply(type).value_counts())
            #         # st.write(expanded_results_df['Region'].apply(type).value_counts())
            #         expanded_TD_results_df['Region'] = expanded_TD_results_df['Region'].apply(
            #                 lambda x: x[0] if isinstance(x, list) else x
            #             )


            #         # Fill NaNs using Brand + Region group means
            #         expanded_TD_results_df['Region_Y_means'] = expanded_TD_results_df.groupby(['Brand', 'Region'])['Region_Y_means'].transform(lambda x: x.fillna(method='ffill').fillna(method='bfill'))


            #         import re
                    
                    
            #         def clean_to_number(text):
            #             try:
            #                 # Extract the first valid number (float or int) from the string
            #                 match = re.search(r'\d+\.\d+|\d+', str(text))
            #                 return float(match.group()) if match else None
            #             except:
            #                 return None

            #         expanded_TD_results_df['Region_Y_means'] = expanded_TD_results_df['Region_Y_means'].apply(clean_to_number)

            #         for col in expanded_TD_results_df.columns:
            #             if col.endswith("_mean") and expanded_TD_results_df[col].dtype == object:
            #                 expanded_TD_results_df[col] = expanded_TD_results_df[col].apply(clean_to_number)
            #                 expanded_TD_results_df[col] = expanded_TD_results_df.groupby(['Brand', 'Region'])[col].transform(
            #                     lambda x: x.fillna(method='ffill').fillna(method='bfill')
            #                 )

            #         # Loop through all beta columns and compute contribution
            #         for col in expanded_TD_results_df.columns:
            #             if col.startswith('beta_'):
            #                 var_name = col.replace('beta_', '')  # get the variable name
            #                 mean_col = f"{var_name}_mean"

            #                 if mean_col in expanded_TD_results_df.columns:
            #                     contribution_col = f"{var_name}_contribution"
            #                     expanded_TD_results_df[contribution_col] = expanded_TD_results_df[col] * expanded_TD_results_df[mean_col]

            #         # Step 2: Collect all contribution columns (excluding beta0 for now)
            #         contribution_cols = [col for col in expanded_TD_results_df.columns if col.endswith('_contribution')]

            #         # Step 3: Add intercept (beta0) as its own contribution
            #         expanded_TD_results_df['beta0_contribution'] = expanded_TD_results_df['beta0']
            #         contribution_cols.append('beta0_contribution')

            #         # Step 4: Calculate total contribution
            #         expanded_TD_results_df['total_contribution'] = expanded_TD_results_df[contribution_cols].sum(axis=1)

            #         # Step 5: Compute percentage contribution for each variable
            #         for col in contribution_cols:
            #             pct_col = col.replace('_contribution', '_pct_contribution')
            #             expanded_TD_results_df[pct_col] = expanded_TD_results_df[col] / expanded_TD_results_df['total_contribution']

            #         # Extract the region name only if it's in list format, otherwise keep the original value
            #         expanded_TD_results_df['Region'] = expanded_TD_results_df['Region'].astype(str).apply(
            #             lambda x: re.findall(r"\['(.*?)'\]", x)[0] if re.findall(r"\['(.*?)'\]", x) else x
            #         )


            #         expanded_TD_results_df['Unique_ID'] = range(1, len(expanded_TD_results_df) + 1)  # Assign unique IDs starting from 1
            #         # expanded_results_df["Approach"] = "Top Down"

            #         # Reorder columns to make Unique_ID the first column
            #         columns = ['Unique_ID'] +  [col for col in expanded_TD_results_df.columns if col != 'Unique_ID']
            #         expanded_TD_results_df = expanded_TD_results_df[columns]

            #         # Drop columns with all NaN values
            #         expanded_TD_results_df = expanded_TD_results_df.dropna(axis=1, how='all')

            #         # Store the expanded results in session_state
            #         st.session_state["expanded_TD_results_df"] = expanded_TD_results_df

            #     # st.write("Modeling completed!")
            # if not st.session_state["expanded_TD_results_df"] is None:
            #     st.dataframe(st.session_state["expanded_TD_results_df"])  # Display results

            # # st.write("Main media variables:",main_media_variables)

        with tab3:

            st.write("final results")
                
            # if "expanded_results_df" in st.session_state:

            #     expanded_results_df =st.session_state["expanded_results_df"] 

            # if "expanded_TD_results_df" in st.session_state:

            #     expanded_TD_results_df =st.session_state["expanded_TD_results_df"] 

            

            #     # st.write("### Bottom Up results with Agg Media beta")

            #     import numpy as np
            #     from sklearn.preprocessing import MinMaxScaler, StandardScaler

            #     # Logistic and adstock functions
            #     def logistic_function(x, growth_rate, midpoint):
            #         return 1 / (1 + np.exp(-growth_rate * (x - midpoint)))

            #     def adstock_function(x, carryover_rate):
            #         """
            #         Applies the adstock transformation to the media variable using the given carryover rate.

            #         Parameters:
            #         - x: The media variable data to apply adstock to (should be a list or numpy array).
            #         - carryover_rate: The carryover rate to apply.

            #         Returns:
            #         - Transformed media variable (numpy array).
            #         """
            #         x = np.array(x)  # Ensure that x is a numpy array
            #         result = np.zeros_like(x)
            #         result[0] = x[0]
            #         for i in range(1, len(x)):
            #             result[i] = x[i] + carryover_rate * result[i - 1]
            #         return result

            #     def apply_transformations_by_region2(df, region_weight_df):
            #         """
            #         Applies adstock, logistic transformations, and standardization to the original DataFrame
            #         based on region weight DataFrame. New media variables inherit the same transformation parameters
            #         as the existing media variables if parameters are uniform.

            #         Parameters:
            #         - df: The DataFrame containing the original data (media and other variables).
            #         - region_weight_df: DataFrame containing region weights and transformation parameters.

            #         Returns:
            #         - DataFrame: Transformed data.
            #         """
            #         transformed_data_list = []  # To store transformed data for each region
            #         unique_regions = region_weight_df["Region"].unique()  # Get unique regions from region_weight_df

            #         # Extract media variables dynamically
            #         media_variables = [
            #             col.replace('beta_', '').replace('_transformed', '')
            #             for col in region_weight_df.columns
            #             if col.startswith('beta_') and '_transformed' in col
            #         ]

            #         # Extract other variables dynamically
            #         other_variables = [
            #             col.replace('beta_', '').replace('scaled_', '')
            #             for col in region_weight_df.columns
            #             if col.startswith('beta_') and 'scaled_' in col
            #         ]

            #         # # Debugging: Print the extracted variable names
            #         # print("Media Variables:", media_variables)
            #         # print("Other Variables:", other_variables)


            #         # Add additional media variables
            #         # additional_media_vars = ['TV_Total_Unique_Reach', 'Digital_Total_Unique_Reach']  # 'Digital_Total_All_Reach', 'TV_Total_All_Reach'
            #         additional_media_vars = main_media_variables
            #         media_variables += additional_media_vars

            #         # Pre-filter the DataFrame for each (Region, Brand) combination
            #         filtered_data = {
            #             (region, brand): df[(df["Region"] == region) & (df["Brand"] == brand)].copy()
            #             for region, brand in region_weight_df[["Region", "Brand"]].drop_duplicates().values
            #         }

            #         # Combine all the filtered data into a single DataFrame
            #         filtered_data_df = pd.concat(filtered_data.values(), axis=0).reset_index(drop=True)

            #         # Stacked the data by Region
            #         if len(unique_regions) == 2:
            #             # Simplify logic for two regions
            #             filtered_data_df = filtered_data_df.groupby("Region").apply(lambda x: x).reset_index(drop=True)
            #         else:
            #             # Default logic for other cases
            #             filtered_data_df = filtered_data_df.groupby("Region").apply(lambda x: x).reset_index(drop=True)


            #         for region in df["Region"].unique():
            #             # Get the specific brand for the current region
            #             # brand = region_weight_df.loc[region_weight_df["Region"] == region, "Brand"].iloc[0]
            #             # Extract scalar values for 'region' and 'brand'
            #             region = row[market_col]  # Assuming 'row' is from .iterrows() and holds scalar values
            #             brand = row['Brand']      # Ensure 'Brand' is also extracted properly

            #             # Access the pre-filtered DataFrame
            #             region_df = filtered_data.get((region, brand), pd.DataFrame())

            #             # Debugging: Check if the DataFrame is empty
            #             if region_df.empty:
            #                 print(f"Warning: No data found for Region={region}, Brand={brand}. Skipping.")
            #                 continue

            #             # Get transformation parameters for the current region from region_weight_df
            #             region_row = region_weight_df[region_weight_df["Region"] == region].iloc[0]

            #             # # Parse parameters into lists
            #             # growth_rates = list(map(float, region_row["Growth_rate"].split(',')))
            #             # carryovers = list(map(float, region_row["Carryover"].split(',')))
            #             # mid_points = list(map(float, region_row["Mid_point"].split(',')))
            #             # # st.write(growth_rates,carryovers,mid_points)

            #             # # Check if all parameters are uniform
            #             # if len(set(growth_rates)) == 1 and len(set(carryovers)) == 1 and len(set(mid_points)) == 1:
            #             #     # Use uniform parameters for all media variables
            #             #     uniform_growth_rate = growth_rates[0]
            #             #     uniform_carryover = carryovers[0]
            #             #     uniform_midpoint = mid_points[0]
            #             #     # st.write(uniform_growth_rate)

            #             #     growth_rates = [uniform_growth_rate] * len(media_variables)
            #             #     carryovers = [uniform_carryover] * len(media_variables)
            #             #     mid_points = [uniform_midpoint] * len(media_variables)
            #             # Fetch transformation type
            #             transformation_type = row.get("Transformation_type", "logistic")

            #             # --- Handle transformation-specific parameters ---
            #             if transformation_type == "logistic":
            #                 growth_rates = list(map(float, str(row.get("Growth_rate", "")).split(',')))
            #                 carryovers = list(map(float, str(row.get("Carryover", "")).split(',')))
            #                 mid_points = list(map(float, str(row.get("Mid_point", "")).split(',')))

            #                 # If uniform, broadcast
            #                 if len(set(growth_rates)) == 1 and len(set(carryovers)) == 1 and len(set(mid_points)) == 1:
            #                     growth_rates *= len(media_variables)
            #                     carryovers *= len(media_variables)
            #                     mid_points *= len(media_variables)

            #             elif transformation_type == "power":
            #                 carryovers = list(map(float, str(row.get("Carryover", "")).split(',')))
            #                 powers = list(map(float, str(row.get("Power", "")).split(',')))

            #                 # If uniform, broadcast
            #                 if len(set(carryovers)) == 1 and len(set(powers)) == 1:
            #                     carryovers *= len(media_variables)
            #                     powers *= len(media_variables)

            #             else:
            #                 raise ValueError(f"Unsupported Transformation_type: {transformation_type}")

            #             standardization_method = region_row["Standardization_method"]

            #             # Choose standardization method
            #             if standardization_method == 'minmax':
            #                 scaler_class = MinMaxScaler
            #                 scaler_params = {'feature_range': (0, 1)}
            #             elif standardization_method == 'zscore':
            #                 scaler_class = StandardScaler
            #                 scaler_params = {}
            #             elif standardization_method == 'none':
            #                 scaler_class = None  # No scaling
            #             else:
            #                 raise ValueError(f"Unsupported standardization method: {standardization_method}")

            #             # Standardize other variables
            #             for var in other_variables:
            #                 if var in region_df.columns:  # Check if the column exists
            #                     if scaler_class:
            #                         scaler = scaler_class(**scaler_params)
            #                         region_df[f"scaled_{var}"] = scaler.fit_transform(region_df[[var]])
            #                     else:
            #                         region_df[f"scaled_{var}"] = region_df[var]  # No scaling

            #             # # Transform media variables
            #             # for idx, media_var in enumerate(media_variables):
            #             #     if media_var in region_df.columns:  # Check if the column exists
            #             #         # Get corresponding parameters
            #             #         growth_rate = growth_rates[idx]
            #             #         carryover = carryovers[idx]
            #             #         mid_point = mid_points[idx]

            #             #         # Apply adstock and logistic transformations
            #             #         adstocked = adstock_function(region_df[media_var].values, carryover)
            #             #         region_df[f"{media_var}_Adstock"] = adstocked
            #             #         standardized = (adstocked - np.mean(adstocked)) / np.std(adstocked)
            #             #         region_df[f"{media_var}_Ad_Std"] = standardized
            #             #         region_df[f"{media_var}_Logistic"] = logistic_function(standardized, growth_rate, mid_point)

            #             #         # Replace NaN values (if any) with 0
            #             #         region_df[f"{media_var}_Logistic"] = np.nan_to_num(region_df[f"{media_var}_Logistic"])

            #             #         if scaler_class:
            #             #             scaler = scaler_class(**scaler_params)
            #             #             region_df[f"{media_var}_transformed"] = scaler.fit_transform(
            #             #                 region_df[[f"{media_var}_Logistic"]]
            #             #             )
            #             # --- Transform media variables ---
            #             for idx_var, media_var in enumerate(media_variables):
            #                 if media_var not in region_df.columns:
            #                     continue

            #                 # Apply carryover/adstock
            #                 carryover = carryovers[idx_var]
            #                 adstocked = adstock_function(region_df[media_var].values, carryover)
            #                 region_df[f"{media_var}_Adstock"] = adstocked

            #                 # Standardize adstocked media
            #                 standardized = (adstocked - np.mean(adstocked)) / np.std(adstocked)
            #                 region_df[f"{media_var}_Ad_Std"] = standardized

            #                 if transformation_type == "logistic":
            #                     growth_rate = growth_rates[idx_var]
            #                     mid_point = mid_points[idx_var]
            #                     transformed = logistic_function(standardized, growth_rate, mid_point)

            #                 elif transformation_type == "power":
            #                     power = powers[idx_var]
            #                     transformed = np.power(np.maximum(standardized, 0), power)

            #                 # Handle NaNs
            #                 transformed = np.nan_to_num(transformed)
            #                 region_df[f"{media_var}_Transformed_Base"] = transformed

            #                 # Apply final standardization
            #                 if scaler_class:
            #                     scaler = scaler_class(**scaler_params)
            #                     region_df[f"{media_var}_transformed"] = scaler.fit_transform(
            #                         region_df[[f"{media_var}_Transformed_Base"]]
            #                     )
            #                 else:
            #                     region_df[f"{media_var}_transformed"] = transformed

            #             # Append the transformed region data to the list
            #             transformed_data_list.append(region_df)

            #         # Concatenate all transformed data
            #         transformed_df = pd.concat(transformed_data_list, axis=0).reset_index(drop=True)
            #         return transformed_df


            #     # Apply transformations
            #     # transformed_df = apply_transformations_by_region2(df, expanded_results_df)
            #     # transformed_df

            #     # st.dataframe(transformed_df)

            #     import pandas as pd
            #     import numpy as np

            #     def calculate_adjusted_betas(transformed_df, weights_df, features, market_col, overall_feature, overall_transform_col):
            #         """
            #         Generalized function to calculate adjusted betas for given features using transformed variables and weights.

            #         Parameters:
            #             transformed_df (DataFrame): DataFrame containing transformed variables.
            #             weights_df (DataFrame): DataFrame containing market weights (betas) for each market.
            #             features (list): List of features for which to calculate adjusted betas.
            #             market_col (str): Column name representing the market.
            #             overall_feature (str): Name of the overall feature to calculate an overall beta (e.g., "TV_All_Adult_Reach").
            #             overall_transform_col (str): Column name for the overall transformed value in `transformed_df`.

            #         Returns:
            #             DataFrame: DataFrame with adjusted betas for each market.
            #         """
            #         market_betas = []

            #         for market in transformed_df[market_col].unique():
            #             # Filter data for the specific market
            #             market_data = transformed_df[transformed_df[market_col] == market]
            #             betas = weights_df[weights_df[market_col] == market].iloc[0]

            #             mean_of_features = []
            #             Betas = []

            #             for feature in features:
            #                 mean_of_feature = market_data[f"{feature}_transformed"].mean()
            #                 beta = betas[f"beta_{feature}_transformed"]

            #                 mean_of_features.append(mean_of_feature)
            #                 Betas.append(beta)

            #             mean_of_features = np.array(mean_of_features)
            #             Betas = np.array(Betas)
            #             result = np.sum(Betas * mean_of_features) / np.sum(mean_of_features)
            #             adjusted_betas = Betas + result
            #             result1 = np.sum(adjusted_betas * mean_of_features) / np.sum(mean_of_features)
            #             scaled_betas = adjusted_betas / (result1/result)

            #             # Calculate the overall beta
            #             mean_transform = market_data[overall_transform_col].mean()
            #             overall_beta = np.sum(scaled_betas * mean_of_features) / mean_transform

            #             # Store results
            #             market_betas.append({
            #                 market_col: market,
            #                 **{feature + '_adjusted': beta for feature, beta in zip(features, scaled_betas)},  # Adjusted betas
            #                 overall_feature + '_adjusted': overall_beta  # Overall adjusted beta
            #             })

            #         return pd.DataFrame(market_betas)



            #     # def merge_results(tv_betas_df, digital_betas_df, weights_df, market_col):
            #     #     """
            #     #     Merge TV, Digital, and other betas into a final DataFrame.

            #     #     Parameters:
            #     #         tv_betas_df (DataFrame): DataFrame with adjusted TV betas.
            #     #         digital_betas_df (DataFrame): DataFrame with adjusted Digital betas.
            #     #         weights_df (DataFrame): DataFrame containing other betas (e.g., price, stores, seasonality).
            #     #         market_col (str): Column name representing the market.

            #     #     Returns:
            #     #         DataFrame: Combined DataFrame with all adjusted betas.
            #     #     """
            #     #     # Merge TV and Digital betas
            #     #     final_df = tv_betas_df.merge(digital_betas_df, on=market_col, how="outer")
            #     #     # st.write(final_df.columns[final_df.columns.duplicated()])
                    

            #     #     # Extract other variables dynamically
            #     #     other_variables = [
            #     #         col.replace('beta_', '').replace('scaled_', '')
            #     #         for col in weights_df.columns
            #     #         if col.startswith('beta_') and 'scaled_' in col
            #     #     ]

            #     #     # Add other betas
            #     #     # other_betas = weights_df[[market_col, 'beta0', 'beta_scaled_D1',
            #     #     # 'beta_scaled_Price', 'beta_scaled_A&P_Amount_Spent',
            #     #     # 'beta_scaled_Region_Brand_seasonality','Growth_rate', 'Carryover', 'Mid_point', 'Standardization_method']]
            #     #     # Generate the column names dynamically
            #     #     if 'Power' in weights_df.columns:
            #     #         other_betas_columns =["Unique_ID",'Model_num',
            #     #                             'Model_type',
            #     #                             'Market',
            #     #                             'Brand',
            #     #                             'Model_selected',
            #     #                             'MAPE',
            #     #                             'Region_MAPEs',  # Assign region-specific MAPE
            #     #                             'R_squared',
            #     #                             'Adjusted_R_squared',
            #     #                             'AIC',
            #     #                             'BIC',
            #     #                             'Y','Power', 'Carryover', 'Standardization_method','Transformation_type'] + [market_col, 'beta0'] + [f'beta_scaled_{var}' for var in other_variables] 
            #     #     else:
            #     #         other_betas_columns =["Unique_ID",'Model_num',
            #     #                             'Model_type',
            #     #                             'Market',
            #     #                             'Brand',
            #     #                             'Model_selected',
            #     #                             'MAPE',
            #     #                             'Region_MAPEs',  # Assign region-specific MAPE
            #     #                             'R_squared',
            #     #                             'Adjusted_R_squared',
            #     #                             'AIC',
            #     #                             'BIC',
            #     #                             'Y','Growth_rate', 'Carryover', 'Mid_point', 'Standardization_method','Transformation_type'] + [market_col, 'beta0'] + [f'beta_scaled_{var}' for var in other_variables] 
            #     #     # Add other betas dynamically
            #     #     other_betas = weights_df[other_betas_columns]
            #     #     final_df = other_betas.merge(final_df, on=market_col, how="outer")

            #     #     return final_df
            #     # if not final_df.empty:
            #     def merge_results(media_betas_dfs, weights_df, market_col):
            #         """
            #         Merge media betas (TV, Digital, etc.) with other betas into a final DataFrame.

            #         Parameters:
            #             media_betas_dfs (list of DataFrames): List of DataFrames with adjusted betas for different media vehicles.
            #             weights_df (DataFrame): DataFrame containing other betas (e.g., price, stores, seasonality).
            #             market_col (str): Column name representing the market.

            #         Returns:
            #             DataFrame: Combined DataFrame with all adjusted betas.
            #         """
            #         from functools import reduce

            #         if not media_betas_dfs:
            #             st.warning("No media betas DataFrames provided.")
            #         else:
            #         # Merge all media vehicle betas into one DataFrame
            #             final_df = reduce(lambda left, right: left.merge(right, on=market_col, how="outer"), media_betas_dfs)

            #             # Extract other variables dynamically
            #             other_variables = [
            #                 col.replace('beta_', '').replace('scaled_', '')
            #                 for col in weights_df.columns
            #                 if col.startswith('beta_') and 'scaled_' in col
            #             ]

            #             # Dynamically select relevant columns
            #             base_cols = ["Unique_ID", 'Model_num', 'Model_type', 'Market', 'Brand', 'Model_selected',
            #                         'MAPE','Avg_MAPE', 'Region_MAPEs', 'R_squared', 'Adjusted_R_squared', 'AIC', 'BIC', 'Y','Region_Y_means',
            #                         'Standardization_method', 'Transformation_type', market_col, 'beta0']
            #             mean_cols = [f"{col}" for col in weights_df.columns if '_mean' in col]
            #             contribution_cols = [f"{col}" for col in weights_df.columns if '_contribution' in col]
            #             pct_contribution_cols = [f"{col}" for col in weights_df.columns if '_pct_contribution' in col]

            #             if 'Power' in weights_df.columns:
            #                 meta_cols = ['Power', 'Carryover']
            #             else:
            #                 meta_cols = ['Growth_rate', 'Carryover', 'Mid_point']

            #             other_betas_columns = base_cols + meta_cols + [f'beta_scaled_{var}' for var in other_variables] + mean_cols + contribution_cols + pct_contribution_cols
            #             other_betas = weights_df[other_betas_columns]

            #             final_df = other_betas.merge(final_df, on=market_col, how="outer")
            #         return final_df

            #     # if not session_state.expanded_results_df.empty:
            #     if expanded_results_df is not None:
            #         media_variables = [
            #                     col.replace('beta_', '').replace('_transformed', '')
            #                     for col in expanded_results_df.columns
            #                     if col.startswith('beta_') and '_transformed' in col
            #                 ]
            #     # media_variables
            #     # # Extract TV and Digital features dynamically from media variable list
            #     # tv_features = [col for col in media_variables if "TV" in col and "Reach" in col]
            #     # digital_features = [col for col in media_variables if "Digital" in col and "Reach" in col]
            #     # Extract TV and Digital features dynamically from media variable list
            #     # tv_features = [col for col in media_variables if "TV" in col ]
            #     # digital_features = [col for col in media_variables if "Digital" in col ]
            #     # tv_features
            #     # digital_features
            #     # Identify main media categories (e.g., "TV", "Digital", "OOH", etc.)
            #     media_categories = list(set(var.split("_")[0] for var in media_variables))
            #     media_genre_dict = {cat: [v for v in media_variables if v.startswith(cat)] for cat in media_categories}
            #     # media_genre_dict

            #     # Print the extracted lists for verification
            #     # st.write("TV Features:", tv_features)
            #     # st.write("Digital Features:", digital_features)
            #     # main_tv = [col for col in main_media_variables if "TV" in col] 
            #     # main_digital = [col for col in main_media_variables if "Digital" in col]
            #     # main_tv
            #     # main_digital
            #     # Identify main media categories (e.g., "TV", "Digital", "OOH", etc.)
            #     main_media_categories = list(set(var.split("_")[0] for var in main_media_variables))
            #     main_media_dict = {cat: [v for v in main_media_variables if v.startswith(cat)] for cat in main_media_categories}
            #     # main_media_dict

            #     market_col = 'Region'
            #     final_results = []

                

            #     # # Iterate through each row in expanded_results_df
            #     # for _, row in expanded_results_df.iterrows():
            #     #     region = row[market_col]

            #     #     # transformed_df = apply_transformations_by_region2(df, expanded_results_df)
                    
            #     #     # # Filter data for the specific region
            #     #     # transformed_region_df = transformed_df[transformed_df[market_col] == region]
            #     #     # expanded_region_df = expanded_results_df[expanded_results_df[market_col] == region]
            #     #     # Ensure we only use the corresponding model row (avoid filtering entire region again)
            #     #     expanded_region_df = pd.DataFrame([row])  # Convert row to DataFrame to keep row structure
            #     #     # expanded_region_df
            #     #     transformed_df = apply_transformations_by_region2(df, expanded_region_df)
                    
            #     #     # Filter data for the specific region
            #     #     transformed_region_df = transformed_df[transformed_df[market_col] == region]
                    
                    
            #     #     # # Calculate adjusted betas for TV and Digital
            #     #     # tv_betas_df = calculate_adjusted_betas(
            #     #     #     transformed_df=transformed_region_df, weights_df=expanded_region_df, 
            #     #     #     features=tv_features, market_col=market_col, 
            #     #     #     overall_feature="TV_Total_Unique_Reach", overall_transform_col="TV_Total_Unique_Reach_transformed"
            #     #     # )
                    
            #     #     # digital_betas_df = calculate_adjusted_betas(
            #     #     #     transformed_df=transformed_region_df, weights_df=expanded_region_df, 
            #     #     #     features=digital_features, market_col=market_col, 
            #     #     #     overall_feature="Digital_Total_Unique_Reach", overall_transform_col="Digital_Total_Unique_Reach_transformed"
            #     #     # )

            #     #     # Calculate adjusted betas for TV and Digital
            #     #     tv_betas_df = calculate_adjusted_betas(
            #     #         transformed_df=transformed_region_df, weights_df=expanded_region_df, 
            #     #         features=tv_features, market_col=market_col, 
            #     #         overall_feature=main_tv[0], overall_transform_col=f"{main_digital[0]}_transformed"
            #     #     )
                    
            #     #     digital_betas_df = calculate_adjusted_betas(
            #     #         transformed_df=transformed_region_df, weights_df=expanded_region_df, 
            #     #         features=digital_features, market_col=market_col, 
            #     #         overall_feature=main_digital[0], overall_transform_col=f"{main_digital[0]}_transformed"
            #     #     )
                    
            #     #     # Merge results for the region
            #     #     final_region_df = merge_results(tv_betas_df, digital_betas_df, expanded_region_df, market_col)
            #     #     # final_results.append(final_region_df)
            #     #     # final_results.extend(final_region_df.to_dict(orient="records"))
            #     #     # Convert row to dictionary and append to final results
            #     #     final_results.append(final_region_df.iloc[0].to_dict())  

                

            #     # # final_results
            #     # # Concatenate results for all regions
            #     # # final_df = pd.concat(final_results, ignore_index=True)
            #     # # Convert list of dictionaries into DataFrame
            #     # final_df = pd.DataFrame(final_results)
            #     # final_df["Approach"] = "Bottom Up"

            #     # # Reorder columns to make Unique_ID the first column
            #     # columns = ["Approach"] +  [col for col in final_df.columns if col != 'Approach']
            #     # final_df = final_df[columns]
            #     # final_df = final_df.fillna(0)

            #     # st.dataframe(final_df)
            #     # # st.write(final_df.columns)
            #     # Iterate through each model row
            #     # if not expanded_results_df.empty:
            #     # if not media_betas_df:
            #     #     st.warning("No media betas DataFrames provided.")
            #     # else:

            #     if expanded_results_df is not None:

            #         for _, row in expanded_results_df.iterrows():
            #             region = row[market_col]
            #             expanded_region_df = pd.DataFrame([row])
            #             transformed_df = apply_transformations_by_region2(df, expanded_region_df)
            #             transformed_region_df = transformed_df[transformed_df[market_col] == region]

            #             media_betas_dfs = []

            #             for media_type in main_media_dict:
            #                 main_features = main_media_dict[media_type]
            #                 all_features = media_genre_dict.get(media_type, [])

            #                 if not main_features or not all_features:
            #                     continue

            #                 main_feature = main_features[0]
            #                 transformed_col = f"{main_feature}_transformed"

            #                 media_beta_df = calculate_adjusted_betas(
            #                     transformed_df=transformed_region_df,
            #                     weights_df=expanded_region_df,
            #                     features=all_features,
            #                     market_col=market_col,
            #                     overall_feature=main_feature,
            #                     overall_transform_col=transformed_col
            #                 )

            #                 media_betas_dfs.append(media_beta_df)

            #             if not media_betas_dfs:
            #                 st.warning(f"No media betas DataFrames provided for region {region}.")
            #             else:

            #                 merged_df = merge_results(media_betas_dfs, expanded_region_df, market_col)
            #                 final_results.append(merged_df)
            #                 # st.write(merged_df.shape)
            #     if not final_results:
            #         st.warning("No media betas DataFrames provided.")
            #     else:
            #         # Combine and format final result
            #         final_df = pd.concat(final_results, ignore_index=True)
            #         # Remove duplicate columns (keep first occurrence)
            #         final_df = final_df.loc[:, ~final_df.columns.duplicated()]
            #         # st.write(final_df)
            #         final_df["Approach"] = "Bottom Up"
            #         final_df = final_df[["Approach"] + [col for col in final_df.columns if col != "Approach"]].fillna(0)
            #         # Store dataframes in session state
            #         if  not final_df.empty:        #'final_df' not in st.session_state and
            #             st.session_state.final_df = final_df.copy()
            #             # st.session_state["final_df"] = final_df

            #     with st.expander("Bottom Up results with Agg Media beta"):
            #         if 'final_df' in st.session_state and not st.session_state.final_df.empty:
            #             st.dataframe(st.session_state.final_df)
            #         else:
            #             st.warning("No Bottom Up results available yet")

            # else:
            #     st.warning("Create the result first.")

        

            # import pandas as pd
            # import numpy as np

            # def apply_transformations_by_region3(df, region_weight_df):
            #     """
            #     Applies adstock, logistic transformations, and standardization to the original DataFrame
            #     based on region weight DataFrame. New media variables inherit the same transformation parameters
            #     as the existing media variables if parameters are uniform.

            #     Parameters:
            #     - df: The DataFrame containing the original data (media and other variables).
            #     - region_weight_df: DataFrame containing region weights and transformation parameters.

            #     Returns:
            #     - DataFrame: Transformed data.
            #     """
            #     transformed_data_list = []  # To store transformed data for each region
            #     unique_regions = region_weight_df["Region"].unique()  # Get unique regions from region_weight_df

            #     # Extract media variables dynamically
            #     media_variables = [
            #         col.replace('_adjusted', '')
            #         for col in region_weight_df.columns
            #         if  '_adjusted' in col
            #     ]

            #     # Extract other variables dynamically
            #     other_variables = [
            #         col.replace('beta_', '').replace('scaled_', '')
            #         for col in region_weight_df.columns
            #         if col.startswith('beta_') and 'scaled_' in col
            #     ]

            #     # # Debugging: Print the extracted variable names
            #     # st.write("Media Variables:", media_variables)
            #     # st.write("Other Variables:", other_variables)


            #     # Add additional media variables
            #     additional_media_vars = main_media_variables  #['TV_Total_Unique_Reach', 'Digital_Total_Unique_Reach']  # 'Digital_Total_All_Reach', 'TV_Total_All_Reach'
            #     media_variables += additional_media_vars

            #     # Pre-filter the DataFrame for each (Region, Brand) combination
            #     filtered_data = {
            #         (region, brand): df[(df["Region"] == region) & (df["Brand"] == brand)].copy()
            #         for region, brand in region_weight_df[["Region", "Brand"]].drop_duplicates().values
            #     }

            #     # Combine all the filtered data into a single DataFrame
            #     filtered_data_df = pd.concat(filtered_data.values(), axis=0).reset_index(drop=True)

            #     # Stacked the data by Region
            #     if len(unique_regions) == 2:
            #         # Simplify logic for two regions
            #         filtered_data_df = filtered_data_df.groupby("Region").apply(lambda x: x).reset_index(drop=True)
            #     else:
            #         # Default logic for other cases
            #         filtered_data_df = filtered_data_df.groupby("Region").apply(lambda x: x).reset_index(drop=True)


            #     for region in df["Region"].unique():
            #         # Get the specific brand for the current region
            #         # brand = region_weight_df.loc[region_weight_df["Region"] == region, "Brand"].iloc[0]
            #         # Extract scalar values for 'region' and 'brand'
            #         region = row[market_col]  # Assuming 'row' is from .iterrows() and holds scalar values
            #         brand = row['Brand']      # Ensure 'Brand' is also extracted properly

            #         # Access the pre-filtered DataFrame
            #         region_df = filtered_data.get((region, brand), pd.DataFrame())

            #         # Debugging: Check if the DataFrame is empty
            #         if region_df.empty:
            #             print(f"Warning: No data found for Region={region}, Brand={brand}. Skipping.")
            #             continue

            #         # Get transformation parameters for the current region from region_weight_df
            #         region_row = region_weight_df[region_weight_df["Region"] == region].iloc[0]

            #         # # Parse parameters into lists
            #         # growth_rates = list(map(float, region_row["Growth_rate"].split(',')))
            #         # carryovers = list(map(float, region_row["Carryover"].split(',')))
            #         # mid_points = list(map(float, region_row["Mid_point"].split(',')))
            #         # # st.write(growth_rates,carryovers,mid_points)

            #         # # Check if all parameters are uniform
            #         # if len(set(growth_rates)) == 1 and len(set(carryovers)) == 1 and len(set(mid_points)) == 1:
            #         #     # Use uniform parameters for all media variables
            #         #     uniform_growth_rate = growth_rates[0]
            #         #     uniform_carryover = carryovers[0]
            #         #     uniform_midpoint = mid_points[0]
            #         #     # st.write(uniform_growth_rate)

            #         #     growth_rates = [uniform_growth_rate] * len(media_variables)
            #         #     carryovers = [uniform_carryover] * len(media_variables)
            #         #     mid_points = [uniform_midpoint] * len(media_variables)
            #         # Fetch transformation type
            #         transformation_type = row.get("Transformation_type", "logistic")

            #         # --- Handle transformation-specific parameters ---
            #         if transformation_type == "logistic":
            #             growth_rates = list(map(float, str(row.get("Growth_rate", "")).split(',')))
            #             carryovers = list(map(float, str(row.get("Carryover", "")).split(',')))
            #             mid_points = list(map(float, str(row.get("Mid_point", "")).split(',')))

            #             # If uniform, broadcast
            #             if len(set(growth_rates)) == 1 and len(set(carryovers)) == 1 and len(set(mid_points)) == 1:
            #                 growth_rates *= len(media_variables)
            #                 carryovers *= len(media_variables)
            #                 mid_points *= len(media_variables)

            #         elif transformation_type == "power":
            #             carryovers = list(map(float, str(row.get("Carryover", "")).split(',')))
            #             powers = list(map(float, str(row.get("Power", "")).split(',')))

            #             # If uniform, broadcast
            #             if len(set(carryovers)) == 1 and len(set(powers)) == 1:
            #                 carryovers *= len(media_variables)
            #                 powers *= len(media_variables)

            #         else:
            #             raise ValueError(f"Unsupported Transformation_type: {transformation_type}")

            #         standardization_method = region_row["Standardization_method"]

            #         # Choose standardization method
            #         if standardization_method == 'minmax':
            #             scaler_class = MinMaxScaler
            #             scaler_params = {'feature_range': (0, 1)}
            #         elif standardization_method == 'zscore':
            #             scaler_class = StandardScaler
            #             scaler_params = {}
            #         elif standardization_method == 'none':
            #             scaler_class = None  # No scaling
            #         else:
            #             raise ValueError(f"Unsupported standardization method: {standardization_method}")

            #         # Standardize other variables
            #         for var in other_variables:
            #             if var in region_df.columns:  # Check if the column exists
            #                 if scaler_class:
            #                     scaler = scaler_class(**scaler_params)
            #                     region_df[f"scaled_{var}"] = scaler.fit_transform(region_df[[var]])
            #                 else:
            #                     region_df[f"scaled_{var}"] = region_df[var]  # No scaling

            #         # # Transform media variables
            #         # for idx, media_var in enumerate(media_variables):
            #         #     if media_var in region_df.columns:  # Check if the column exists
            #         #         # Get corresponding parameters
            #         #         growth_rate = growth_rates[idx]
            #         #         carryover = carryovers[idx]
            #         #         mid_point = mid_points[idx]

            #         #         # Apply adstock and logistic transformations
            #         #         adstocked = adstock_function(region_df[media_var].values, carryover)
            #         #         region_df[f"{media_var}_Adstock"] = adstocked
            #         #         standardized = (adstocked - np.mean(adstocked)) / np.std(adstocked)
            #         #         region_df[f"{media_var}_Ad_Std"] = standardized
            #         #         region_df[f"{media_var}_Logistic"] = logistic_function(standardized, growth_rate, mid_point)

            #         #         # Replace NaN values (if any) with 0
            #         #         region_df[f"{media_var}_Logistic"] = np.nan_to_num(region_df[f"{media_var}_Logistic"])

            #         #         if scaler_class:
            #         #             scaler = scaler_class(**scaler_params)
            #         #             region_df[f"{media_var}_transformed"] = scaler.fit_transform(
            #         #                 region_df[[f"{media_var}_Logistic"]]
            #         #             )
            #         # --- Transform media variables ---
            #         for idx_var, media_var in enumerate(media_variables):
            #             if media_var not in region_df.columns:
            #                 continue

            #             # Apply carryover/adstock
            #             carryover = carryovers[idx_var]
            #             adstocked = adstock_function(region_df[media_var].values, carryover)
            #             region_df[f"{media_var}_Adstock"] = adstocked

            #             # Standardize adstocked media
            #             standardized = (adstocked - np.mean(adstocked)) / np.std(adstocked)
            #             region_df[f"{media_var}_Ad_Std"] = standardized

            #             if transformation_type == "logistic":
            #                 growth_rate = growth_rates[idx_var]
            #                 mid_point = mid_points[idx_var]
            #                 transformed = logistic_function(standardized, growth_rate, mid_point)

            #             elif transformation_type == "power":
            #                 power = powers[idx_var]
            #                 transformed = np.power(np.maximum(standardized, 0), power)

            #             # Handle NaNs
            #             transformed = np.nan_to_num(transformed)
            #             region_df[f"{media_var}_Transformed_Base"] = transformed

            #             # Apply final standardization
            #             if scaler_class:
            #                 scaler = scaler_class(**scaler_params)
            #                 region_df[f"{media_var}_transformed"] = scaler.fit_transform(
            #                     region_df[[f"{media_var}_Transformed_Base"]]
            #                 )
            #             else:
            #                 region_df[f"{media_var}_transformed"] = transformed

            #         # Append the transformed region data to the list
            #         transformed_data_list.append(region_df)

            #     # Concatenate all transformed data
            #     transformed_df = pd.concat(transformed_data_list, axis=0).reset_index(drop=True)
            #     return transformed_df



            # # def compute_genre_ratios(row, transformed_df):
            # #     """Compute genre ratios for a given row and transformed DataFrame."""
            # #     unique_id = row['Unique_ID']
            # #     region = row['Region']

            # #     # Extract genre betas
            # #     genre_betas_tv = row[[f"{var}_adjusted" for var in media_variables if var.startswith("TV")]].values
            # #     # genre_betas_tv

            # #     genre_betas_digital = row[[f"{var}_adjusted" for var in media_variables if var.startswith("Digital")]].values

            # #     # Mean values for transformed genres
            # #     mean_tv_genres = transformed_df.loc[
            # #         transformed_df['Region'] == region,
            # #         [f"{var}_transformed" for var in media_variables if var.startswith("TV")]].mean().values
            # #     # st.write(mean_tv_genres)

            # #     mean_digital_genres = transformed_df.loc[
            # #         transformed_df['Region'] == region,
            # #         [f"{var}_transformed" for var in media_variables if var.startswith("Digital")]].mean().values

            # #     # Contribution ratios
            # #     weighted_tv_contributions = genre_betas_tv * mean_tv_genres
            # #     weighted_digital_contributions = genre_betas_digital * mean_digital_genres

            # #     # Zero check for TV
            # #     tv_total_sum = weighted_tv_contributions.sum()
            # #     tv_contribution_ratio = weighted_tv_contributions / tv_total_sum if tv_total_sum != 0 else np.zeros_like(weighted_tv_contributions)

            # #     # Zero check for Digital
            # #     digital_total_sum = weighted_digital_contributions.sum()
            # #     digital_contribution_ratio = weighted_digital_contributions / digital_total_sum if digital_total_sum != 0 else np.zeros_like(weighted_digital_contributions)


            # #     return {
            # #         'unique_id': unique_id,
            # #         'tv_ratio': tv_contribution_ratio,
            # #         'digital_ratio': digital_contribution_ratio
            # #     }
            
            
            
            # # # if final_df is not None:

            # # def calculate_genre_ratios(final_df, df):
            # #     """Iterate through rows and calculate genre ratios using compute_genre_ratios()."""
            # #     genre_ratios = {}

            # #     for idx, row in final_df.iterrows():
            # #         transformed_df = apply_transformations_by_region3(df, pd.DataFrame([row]))

            # #         if transformed_df.empty:
            # #             print(f"Warning: Transformed DataFrame is empty for Region={row['Region']} and Unique_ID={row['Unique_ID']}")
            # #             continue  # Skip calculations for this row if data is empty

            # #         ratios = compute_genre_ratios(row, transformed_df)
            # #         genre_ratios[ratios['unique_id']] = {
            # #             'tv_ratio': ratios['tv_ratio'],
            # #             'digital_ratio': ratios['digital_ratio']
            # #         }

            # #     return genre_ratios



            # # genre_ratios_list = []  # Initialize list to store genre ratios for each row

            # # # Iterate through each row in expanded_results_df
            # # for _, row in final_df.iterrows():
            # #     region = row[market_col]

            # #     # Convert row to DataFrame to retain structure
            # #     expanded_region_df = pd.DataFrame([row])  
            # #     # st.write(expanded_region_df)

            # #     # Apply transformations using the refined function
            # #     transformed_df = apply_transformations_by_region3(df, expanded_region_df)
            # #     # st.write(transformed_df.columns)

            # #     # Filter data for the specific region
            # #     transformed_region_df = transformed_df[transformed_df[market_col] == region]

            # #     # Calculate genre ratios
            # #     genre_ratios = compute_genre_ratios(row, transformed_region_df)

                
            # #     # Append calculated genre ratios with Unique_ID for merging
            # #     genre_ratios['unique_id'] = row['Unique_ID']
            # #     genre_ratios_list.append(genre_ratios)

            # # # Convert the list of dictionaries to DataFrame
            # # genre_ratios_df = pd.DataFrame(genre_ratios_list)
            # def compute_genre_ratios(row, transformed_df):
            #     """Compute genre ratios for all media types in a given row and transformed DataFrame."""
            #     unique_id = row['Unique_ID']
            #     region = row[market_col]
            #     genre_ratios = {}

            #     for media_type, genre_vars in media_genre_dict.items():
            #         genre_betas = row[[f"{var}_adjusted" for var in genre_vars]].values
            #         transformed_cols = [f"{var}_transformed" for var in genre_vars]

            #         # Mean transformed values for the current region
            #         mean_transformed = transformed_df.loc[
            #             transformed_df[market_col] == region,
            #             transformed_cols
            #         ].mean().values

            #         # Weighted contributions and normalized ratios
            #         weighted_contributions = genre_betas * mean_transformed
            #         total = weighted_contributions.sum()
            #         ratio = weighted_contributions / total if total != 0 else np.zeros_like(weighted_contributions)

            #         genre_ratios[f"{media_type}_ratio"] = ratio

            #     return {
            #         'unique_id': unique_id,
            #         'genre_ratios': genre_ratios
            #     }

            # def calculate_genre_ratios(final_df, df):
            #     """Calculate genre ratios across all model rows."""
            #     genre_ratios_list = []

            #     for _, row in final_df.iterrows():
            #         region = row[market_col]

            #         # Transform input data for the specific row
            #         transformed_df = apply_transformations_by_region3(df, pd.DataFrame([row]))

            #         if transformed_df.empty:
            #             print(f"Warning: Transformed DataFrame is empty for Region={region} and Unique_ID={row['Unique_ID']}")
            #             continue

            #         # Compute and store genre ratios
            #         genre_ratio_result = compute_genre_ratios(row, transformed_df)
            #         genre_ratios_list.append(genre_ratio_result)

            #     # Flatten dictionary list into a DataFrame
            #     genre_ratios_df = []
            #     for item in genre_ratios_list:
            #         flat_row = {'Unique_ID': item['unique_id']}
            #         for media_type, ratios in item['genre_ratios'].items():
            #             for i, val in enumerate(ratios):
            #                 flat_row[f"{media_type}_{i}"] = val
            #         genre_ratios_df.append(flat_row)

            #     return pd.DataFrame(genre_ratios_df)


            # # genre_ratios_df = calculate_genre_ratios(final_df, df)
            # # genre_ratios_df


            # # def redistribute_genre_betas_generalized(result_df, genre_ratios):
            # #     """
            # #     Generalized redistribution of genre-level betas from total TV and Digital betas.

            # #     Parameters:
            # #         result_df (DataFrame): Contains 'Unique_ID' and total beta values.
            # #         genre_ratios (dict): Dictionary with 'unique_id', 'tv_ratio', and 'digital_ratio'.
            # #         media_variables (list): List of all media genre variables (e.g., ['TV_Cricket_Unique_Reach', ...])

            # #     Returns:
            # #         DataFrame: with redistributed genre betas and renamed total columns.
            # #     """
            # #     uid = genre_ratios.get('unique_id', genre_ratios.get('Unique_ID'))
            # #     if uid is None:
            # #         raise KeyError("Genre ratios dictionary must contain 'unique_id' or 'Unique_ID'.")

            # #     tv_vars = [var for var in media_variables if var.startswith("TV")]
            # #     digital_vars = [var for var in media_variables if var.startswith("Digital")]

            # #     tv_ratio = np.array(eval(genre_ratios['tv_ratio'])) if isinstance(genre_ratios['tv_ratio'], str) else np.array(genre_ratios['tv_ratio'])
            # #     digital_ratio = np.array(eval(genre_ratios['digital_ratio'])) if isinstance(genre_ratios['digital_ratio'], str) else np.array(genre_ratios['digital_ratio'])

            # #     genre_ratios_df = pd.DataFrame({
            # #         'Unique_ID': [str(uid)],
            # #         'tv_ratio': [tv_ratio],
            # #         'digital_ratio': [digital_ratio]
            # #     })

            # #     result_df['Unique_ID'] = result_df['Unique_ID'].astype(str)
            # #     filtered_result_df = result_df[result_df['Unique_ID'] == str(uid)].copy()
            # #     if filtered_result_df.empty:
            # #         raise ValueError(f"No rows found in result_df for Unique_ID {uid}")

            # #     merged_df = filtered_result_df.merge(genre_ratios_df, on='Unique_ID', how='left')

            # #     def compute_adjusted(row):
            # #         # tv_total = row.get('beta_TV_Total_Unique_Reach_transformed', 0)
            # #         # digital_total = row.get('beta_Digital_Total_Unique_Reach_transformed', 0)
            # #         tv_total = row.get([f"beta_{var}_transformed" for var in main_media_variables if var.startswith("TV")][0], 0)
            # #         digital_total = row.get([f"beta_{var}_transformed" for var in main_media_variables if var.startswith("Digital")][0], 0)

            # #         tv_adjusted = tv_total * np.array(row['tv_ratio'])
            # #         digital_adjusted = digital_total * np.array(row['digital_ratio'])

            # #         adjusted_values = {}
            # #         for i, var in enumerate(tv_vars):
            # #             adjusted_values[f"{var}_adjusted"] = tv_adjusted[i]

            # #         for i, var in enumerate(digital_vars):
            # #             adjusted_values[f"{var}_adjusted"] = digital_adjusted[i]

            # #         return pd.Series(adjusted_values)

            # #     adjusted_df = merged_df.apply(compute_adjusted, axis=1)

            # #     final_df = pd.concat([merged_df, adjusted_df], axis=1).copy()

            # #     # Generalized renaming of total media columns
            # #     rename_map = {
            # #         f"beta_{media}_transformed": f"{media}_adjusted"
            # #         for media in main_media_variables
            # #         if f"beta_{media}_transformed" in final_df.columns
            # #     }
            # #     final_df2 = final_df.rename(columns=rename_map)

            # #     return final_df2
            

            # def redistribute_genre_betas_flexible(result_df, genre_ratios, media_variables, main_media_variables, verbose=True):
            #     """
            #     Generalized redistribution of genre-level betas for any number of media vehicles.

            #     Parameters:
            #         result_df (pd.DataFrame): DataFrame containing beta values.
            #         genre_ratios (dict): Must include 'unique_id' or 'Unique_ID' and ratio arrays for each media vehicle.
            #                             Example: {'unique_id': 'model_1', 'TV': [...], 'Digital': [...], 'Radio': [...]}
            #                             It can also contain nested 'genre_ratios' key, in which case the function will handle it.
            #         media_variables (list): List of all genre-level media variables (e.g., ['TV_Cricket', 'TV_Movie', ...])
            #         main_media_variables (list): List of total-level media variables (e.g., ['TV_Total', 'Digital_Total'])

            #     Returns:
            #         pd.DataFrame: DataFrame with redistributed genre betas and renamed total beta columns.
            #     """
            #     import numpy as np
            #     import pandas as pd

            #     # --- Flatten genre_ratios if nested ---
            #     if 'genre_ratios' in genre_ratios:
            #         flat = {'unique_id': genre_ratios.get('unique_id', genre_ratios.get('Unique_ID'))}
            #         for k, v in genre_ratios['genre_ratios'].items():
            #             vehicle = k.replace("_ratio", "")
            #             flat[vehicle] = np.array(eval(v)) if isinstance(v, str) else np.array(v)
            #         genre_ratios = flat

            #     uid = genre_ratios.get('unique_id', genre_ratios.get('Unique_ID'))
            #     if uid is None:
            #         raise KeyError("Genre ratios dictionary must contain 'unique_id' or 'Unique_ID'.")

            #     media_vehicles = [key for key in genre_ratios if key not in ['unique_id', 'Unique_ID']]

            #     media_genre_dict = {
            #         vehicle: [var for var in media_variables if var.startswith(vehicle + "_")]
            #         for vehicle in media_vehicles
            #     }

            #     main_media_dict = {
            #         vehicle: [var for var in main_media_variables if var.startswith(vehicle + "_")]
            #         for vehicle in media_vehicles
            #     }

            #     result_df['Unique_ID'] = result_df['Unique_ID'].astype(str)
            #     filtered_result_df = result_df[result_df['Unique_ID'] == str(uid)].copy()
            #     if filtered_result_df.empty:
            #         raise ValueError(f"No rows found in result_df for Unique_ID {uid}")

            #     # Prepare genre ratios DataFrame
            #     ratio_data = {'Unique_ID': [str(uid)]}
            #     for vehicle in media_vehicles:
            #         ratio_array = genre_ratios[vehicle]
            #         ratio_data[f'{vehicle}_ratio'] = [np.array(ratio_array)]
            #     genre_ratios_df = pd.DataFrame(ratio_data)

            #     merged_df = filtered_result_df.merge(genre_ratios_df, on='Unique_ID', how='left')

            #     def compute_adjusted(row):
            #         adjusted_values = {}

            #         for vehicle in media_vehicles:
            #             try:
            #                 main_media = main_media_dict[vehicle][0]
            #             except IndexError:
            #                 if verbose:
            #                     print(f"[WARN] No total variable found for vehicle: {vehicle}")
            #                 continue

            #             total_col = f'beta_{main_media}_transformed'
            #             if total_col not in row:
            #                 if verbose:
            #                     print(f"[WARN] Column '{total_col}' missing in row.")
            #                 continue

            #             total_beta = row.get(total_col, 0)
            #             if verbose:
            #                 print(f"[INFO] Vehicle: {vehicle}, Total: {total_col} = {total_beta}")

            #             ratio = row.get(f'{vehicle}_ratio')
            #             genre_vars = media_genre_dict.get(vehicle, [])

            #             if len(ratio) != len(genre_vars):
            #                 raise ValueError(f"[ERROR] Length mismatch: {vehicle} ratio ({len(ratio)}) vs genre_vars ({len(genre_vars)}): {genre_vars}")

            #             adjusted_betas = total_beta * np.array(ratio)
            #             for i, var in enumerate(genre_vars):
            #                 adjusted_values[f'{var}_adjusted'] = adjusted_betas[i]

            #         return pd.Series(adjusted_values)

            #     adjusted_df = merged_df.apply(compute_adjusted, axis=1)

            #     if adjusted_df.empty and verbose:
            #         print("[WARN] Adjusted DataFrame is empty. Check for issues in beta columns or media variable naming.")

            #     final_df = pd.concat([merged_df, adjusted_df], axis=1)

            #     # Rename beta columns
            #     rename_map = {
            #         f'beta_{media}_transformed': f'{media}_adjusted'
            #         for media in main_media_variables
            #         if f'beta_{media}_transformed' in final_df.columns
            #     }
            #     final_df2 = final_df.rename(columns=rename_map)

            #     return final_df2





            # if 'final_df' in st.session_state and not st.session_state.final_df.empty:

            #     redistributed_dfs = []

            #     for _, row in st.session_state.final_df.iterrows():
            #         region = row[market_col]
                    
            #         # Convert the single row into a DataFrame
            #         expanded_region_df = pd.DataFrame([row])
                    
            #         # Apply transformations using your function (apply_transformations_by_region3)
            #         transformed_df = apply_transformations_by_region3(df, expanded_region_df)
                    
            #         # Filter transformed data for the specific region
            #         transformed_region_df = transformed_df[transformed_df[market_col] == region]
                    
            #         # Compute genre ratios for this row using the filtered transformed data
            #         gr = compute_genre_ratios(row, transformed_region_df)
            #         # Add the unique identifier (if not already present)
            #         gr['unique_id'] = row['Unique_ID']
            #         # st.write("media genre ratios:",gr)
                    
            #         # Use the redistribution function on the full result DataFrame for this Unique_ID
            #         redistributed_df = redistribute_genre_betas_flexible(expanded_TD_results_df, gr, media_variables, main_media_variables)
                    
            #         redistributed_dfs.append(redistributed_df)
            #     # for _, row in final_df.iterrows():
            #     #     region = row[market_col]
            #     #     expanded_region_df = pd.DataFrame([row])

            #     #     # Apply transformations using your function (apply_transformations_by_region3)
            #     #     transformed_df = apply_transformations_by_region3(df, expanded_region_df)

            #     #     # Filter transformed data for the specific region
            #     #     transformed_region_df = transformed_df[transformed_df[market_col] == region]

            #     #     # Compute genre ratios for this row using the filtered transformed data
            #     #     gr = compute_genre_ratios(row, transformed_region_df)
            #     #     gr['unique_id'] = row['Unique_ID']

            #     #     # Use the redistribution function on the full result DataFrame for this Unique_ID
            #     #     redistributed_df = redistribute_genre_betas_generalized(
            #     #         expanded_TD_results_df, gr, media_variables, main_media_variables
            #     #     )

            #     #     redistributed_dfs.append(redistributed_df)

            #     # # Combine all redistributed DataFrames into one final DataFrame
            #     final_combined_df = pd.concat(redistributed_dfs, ignore_index=True)
            #     final_combined_df["Approach"] = "Top Down"

            #     # Define fixed/common columns
            #     fixed_columns = [
            #         "Approach", "Unique_ID", "Model_num", "Model_type", "Market", "Brand", "Region",
            #         "Model_selected", "MAPE", "Region_MAPEs", "R_squared", "Adjusted_R_squared",
            #         "AIC", "BIC","Standardization_method","Transformation_type", "Y", "beta0"
            #     ]

            #     beta_scaled_columns = [col for col in final_combined_df.columns if col.startswith("beta_scaled_")]

            #     # Collect all adjusted media columns dynamically
            #     adjusted_columns = [col for col in final_combined_df.columns if col.endswith("_adjusted")]

            #     if 'Power' in final_combined_df.columns:

            #         # Transformation-related and other meta columns
            #         meta_columns = ["Power", "Carryover",  "tv_ratio", "digital_ratio"]
            #     else:
            #         # Transformation-related and other meta columns
            #         meta_columns = ["Growth_rate", "Mid_point", "Carryover", "tv_ratio", "digital_ratio"]

            #     # Combine all columns for final ordering
            #     final_columns = fixed_columns + beta_scaled_columns + adjusted_columns + meta_columns

            #     # Keep only available columns to avoid KeyErrors
            #     final_columns_filtered = [col for col in final_columns if col in final_combined_df.columns]

            #     # Reorder columns accordingly
            #     final_combined_df = final_combined_df[final_columns_filtered]

            #     # Label this set as Top Down
            #     # final_combined_df["Approach"] = "Top Down"

            #     if  not final_combined_df.empty:               #'final_combined_df' not in st.session_state and
            #         st.session_state.final_combined_df = final_combined_df

            #     with st.expander("Top Down results with genre beta"):

            #         # if not final_combined_df.empty:

            #         if 'final_combined_df' in st.session_state and not st.session_state.final_combined_df.empty:
            #             st.write("### Top down results with genre beta")
            #             st.dataframe(st.session_state.final_combined_df)
            #         else:
            #             st.warning("No Top Down results available yet")

            #     # Concatenate with Bottom Up (or original final_df)
            #     TD_BU_df = pd.concat([st.session_state.final_df, final_combined_df], ignore_index=True)

            #     if  not TD_BU_df.empty:                   #'TD_BU_df' not in st.session_state and
            #         st.session_state.TD_BU_df = TD_BU_df


            #     if 'TD_BU_df' in st.session_state and not st.session_state.TD_BU_df.empty:
            #         st.write("### Top down and Bottom up results")
            #         st.dataframe(st.session_state.TD_BU_df)
            #     else:
            #         st.warning("No combined Top Down/Bottom Up results available yet")


######################################################################## EVALUATE PAGE ######################################################################################
######################################################################## EVALUATE PAGE ######################################################################################
######################################################################## EVALUATE PAGE ######################################################################################
######################################################################## EVALUATE PAGE ######################################################################################
######################################################################## EVALUATE PAGE ######################################################################################



if selected == "EVALUATE":
    import streamlit as st
    import pandas as pd
    import numpy as np
    import matplotlib.pyplot as plt
    from sklearn.preprocessing import StandardScaler, MinMaxScaler
    import plotly.graph_objects as go
    import io
    import plotly.express as px

    # # Restrict access
    # if "authenticated" not in st.session_state or not st.session_state.authenticated:
    #     st.error("Unauthorized access! Please log in from the main page.")
    #     st.stop()  # 🚫 Stop further execution if user is not logged in

    # st.set_page_config(layout="wide") 
    # st.title("Model Selection")

    col1, col2 = st.columns(2)

    # with col1:

    uploaded_D1_file = st.sidebar.file_uploader("Upload file used for Modeling", type=["csv", "xlsx"])

    if uploaded_D1_file:
        try:
            # Load the dataset
            if uploaded_D1_file.name.endswith(".csv"):
                df = pd.read_csv(uploaded_D1_file)
            else:
                df = pd.read_excel(uploaded_D1_file)

        except Exception as e:
            st.error(f"Error loading file: {e}")

    # if 'df' in st.session_state and not st.session_state.df.empty:
    #     # st.write("### Top down results with genre beta")
    #     df = st.session_state.df
    # else:
    #     st.warning("No data available yet")

    # with col2:

    uploaded_M0_file = st.sidebar.file_uploader("Upload M0 file", type=["csv", "xlsx"])

    # if uploaded_M0_file:
    #     try:
    #         # Load the dataset
    #         if uploaded_M0_file.name.endswith(".csv"):
    #             M0 = pd.read_csv(uploaded_M0_file)
    #         else:
    #             M0 = pd.read_excel(uploaded_M0_file)

    #     except Exception as e:
    #         st.error(f"Error loading file: {e}")

    if uploaded_M0_file:
        try:
            if uploaded_M0_file.name.endswith(".csv"):
                M0 = pd.read_csv(uploaded_M0_file)

            else:
                # Load Excel file and list available sheets
                excel_file = pd.ExcelFile(uploaded_M0_file)
                sheet_names = excel_file.sheet_names

                # Let user select a sheet
                selected_sheet = st.sidebar.selectbox("Select sheet", sheet_names)

                # Load the selected sheet
                M0 = pd.read_excel(excel_file, sheet_name=selected_sheet)

            # st.success("File loaded successfully.")

        except Exception as e:
            st.error(f"Error loading file: {e}")

        # Example: Assuming your dataframe is called df
        M0.rename(columns={col: col.replace('beta_', '').replace('_transformed', '_adjusted') 
            for col in M0.columns if col.endswith('_transformed') and col.startswith('beta_')}, inplace=True)
        M0["Unique_ID"] = range(1, len(M0) + 1)
        M0["Approach"] = "Bottom UP"
        M0["Model_num"] = range(1, len(M0) + 1)
        M0["Model_type"] = "Weighted Model"

        # Assuming market_weight_df is your DataFrame
        market_weight_columns = M0.columns.tolist()
        # st.write(market_weight_columns)

    # if 'TD_BU_df' in st.session_state and not st.session_state.TD_BU_df.empty:
    #         # st.write("### Top down and Bottom up results")
    #         # st.dataframe(st.session_state.TD_BU_df)
    #     M0 = st.session_state.TD_BU_df

        # st.dataframe(df)

        st.markdown(
                """ 
                <div style="height: 2px; background-color: black; margin: 10px 0;"></div>
                """, 
                unsafe_allow_html=True
                )

        col5, col6 = st.columns(2)

        # Session state variable to store selected models across different regions
        # Initialize session state for storing selected models
        if "selected_models_df" not in st.session_state:
            st.session_state.selected_models_df = pd.DataFrame()

        # Initialize session state variables
        if "selection_locked" not in st.session_state:
            st.session_state.selection_locked = False  # False means selection is open

        with col5:

            # Main content for user selection
            st.header("Model Selection")
            col3, col4 = st.columns(2)
            with col3:
                selected_region = st.selectbox("Select Region", M0['Region'].unique())
                if 'Power' in M0.columns:
                    selected_power = st.multiselect("Select Power", M0["Power"].unique(), default=M0["Power"].unique())
                else:
                    selected_gr = st.multiselect("Select Media Growth rate", M0["Growth_rate"].unique(), default=M0["Growth_rate"].unique())
            with col4:
                selected_brand = st.selectbox("Select Brand", M0['Brand'].unique())
                selected_co = st.multiselect("Select Carryover", M0["Carryover"].unique(), default=M0["Carryover"].unique())

            # Filter the data
            filtered_data = df[(df['Region'] == selected_region) & (df['Brand'] == selected_brand)]
            if 'Power' in M0.columns:
                filtered_model_results = M0[
                    (M0['Region'] == selected_region) & 
                    (M0['Brand'] == selected_brand) &
                    (M0['Power'].isin(selected_power)) &
                    (M0['Carryover'].isin(selected_co))
                ]
            else:
                filtered_model_results = M0[
                        (M0['Region'] == selected_region) & 
                        (M0['Brand'] == selected_brand) &
                        (M0['Growth_rate'].isin(selected_gr)) &
                        (M0['Carryover'].isin(selected_co))
                    ]

            # Display filtered data
            st.subheader(f"Filtered Data for Region: {selected_region} | Brand: {selected_brand}")
            # st.dataframe(filtered_data)
            # st.dataframe(filtered_model_results)

            filtered_data["Year"] = pd.to_numeric(filtered_data["Year"], errors="coerce")

            # Drop rows with invalid Year values
            filtered_data = filtered_data.dropna(subset=["Year"])

            # Convert Year to integer
            filtered_data["Year"] = filtered_data["Year"].astype(int)

            # filtered_data["Date"] = pd.to_datetime(
            #             filtered_data["Year"].astype(str) + "-" + filtered_data["Month"],
            #             format="%Y-%B",
            #             errors="coerce"
            #         )
            filtered_data = filtered_data.sort_values(by=["Date"])
            # filtered_data
            
            # Function to format values as M (millions) or K (thousands)
            def format_value(x):
                return f"{x / 1e6:.1f}M" if x >= 1e6 else f"{x / 1e3:.1f}K"

            # Extract media variables dynamically
            media_variables = [
                col.replace('_adjusted', '') for col in filtered_model_results.columns if col.endswith('_adjusted')
            ]
            # media_variables

            # Extract other variables dynamically
            other_variables = [
                col.replace('beta_scaled_', '') for col in filtered_model_results.columns if col.startswith('beta_scaled_')
            ]

            # Combine both variable lists for plotting
            selected_columns = media_variables + other_variables

            # Check if the required columns exist in the DataFrame
            available_columns = [col for col in selected_columns if col in filtered_data.columns]

            if available_columns:
                # Melt the DataFrame for visualization
                df_melted = filtered_data.melt(id_vars=["Fiscal Year", "Region"], value_vars=selected_columns, 
                                        var_name="Metric", value_name="Value")
                # df_melted = df_melted.groupby(["Fiscal Year", "Region", "Metric"], as_index=False)["Value"].sum()
                df_melted = df_melted.groupby(["Fiscal Year", "Region", "Metric"], as_index=False).agg(
                    Value=("Value", lambda x: x.mean() if x.name == "Value" and "Price" in df_melted.loc[x.index, "Metric"].values else x.sum())
                )

                # Apply formatting
                df_melted["Formatted_Value"] = df_melted["Value"].apply(format_value)

                # Function to clean metric names
                def clean_metric_name(metric):
                    words = metric.replace("_", " ").split()  
                    return " ".join(words[:2])  # Keep only the first two words
                
                df_melted["Metric"] = df_melted["Metric"].apply(clean_metric_name)  

                # Plot the bar chart
                fig = px.bar(df_melted, 
                            x="Value", 
                            y="Metric", 
                            color="Fiscal Year", 
                            barmode="group",
                            facet_col="Region",  
                            text=df_melted["Formatted_Value"],  
                            title="Independent Variables")

                st.plotly_chart(fig)
            else:
                print("Error: No valid media or other variables found in the DataFrame.")

            # filtered_data.columns

            # Check if the required columns exist in the DataFrame
            amount_spent_variables = [
                f"{'_'.join(var.split('_')[:-1])}_Cost" if '_' in var else f"{var}_Cost"
                for var in media_variables
            ]
            # amount_spent_variables
            # st.write(amount_spent_variables)
            available_columns_amount_spent = [col for col in amount_spent_variables if col in filtered_data.columns]
            # available_columns_amount_spent

            if available_columns_amount_spent:
                # Melt the DataFrame for visualization
                df_melted = filtered_data.melt(id_vars=["Fiscal Year", "Region"], value_vars=amount_spent_variables, 
                                        var_name="Metric", value_name="Value")
                # df_melted = df_melted.groupby(["Fiscal Year", "Region", "Metric"], as_index=False)["Value"].sum()
                df_melted = df_melted.groupby(["Fiscal Year", "Region", "Metric"], as_index=False).agg(
                    Value=("Value", lambda x: x.mean() if x.name == "Value" and "Price" in df_melted.loc[x.index, "Metric"].values else x.sum())
                )
                # df_melted

                # Apply formatting
                df_melted["Formatted_Value"] = df_melted["Value"].apply(format_value)

                # Function to clean metric names
                def clean_metric_name(metric):
                    words = metric.replace("_", " ").split()  
                    return " ".join(words[:3])  # Keep only the first two words
                
                df_melted["Metric"] = df_melted["Metric"].apply(clean_metric_name)  

                # Plot the bar chart
                fig = px.bar(df_melted, 
                            x="Value", 
                            y="Metric", 
                            color="Fiscal Year", 
                            barmode="group",
                            facet_col="Region",  
                            text=df_melted["Formatted_Value"],  
                            title="Media Amount Spent")

                st.plotly_chart(fig)
            else:
                print("Error: No valid media or other variables found in the DataFrame.")

            


            # Define adstock and logistic functions
            # Logistic and adstock functions
            def logistic_function(x, growth_rate, midpoint):
                return 1 / (1 + np.exp(-growth_rate * (x - midpoint)))

            def adstock_function(x, carryover_rate):
                """
                Applies the adstock transformation to the media variable using the given carryover rate.

                Parameters:
                - x: The media variable data to apply adstock to (should be a list or numpy array).
                - carryover_rate: The carryover rate to apply.

                Returns:
                - Transformed media variable (numpy array).
                """
                x = np.array(x)  # Ensure that x is a numpy array
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
                unique_regions = df["Region"].unique()

                # Extract media variables dynamically
                media_variables = [
                    col.replace('_adjusted', '')
                    for col in region_weight_df.columns
                    if col.endswith('_adjusted') 
                ]

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

                # # Add additional media variables
                # additional_media_vars = ['TV_Total_Unique_Reach', 'Digital_Total_Unique_Reach']
                # media_variables += additional_media_vars

                # Filter data by Region and Brand
                filtered_data = {
                region: df[df["Region"] == region].copy() for region in unique_regions
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

                    # # Transform media variables and calculate contributions
                    # for idx, media_var in enumerate(media_variables):
                    #     if media_var in region_df.columns:
                    #         growth_rate = growth_rates[idx]
                    #         carryover = carryovers[idx]
                    #         mid_point = mid_points[idx]
                    #         beta_col = f"{media_var}_adjusted"

                    #         adstocked = adstock_function(region_df[media_var].values, carryover)
                    #         standardized = (adstocked - np.mean(adstocked)) / np.std(adstocked)
                    #         transformed = logistic_function(standardized, growth_rate, mid_point)
                    #         transformed = np.nan_to_num(transformed)

                    #         if scaler_class:
                    #             scaler = scaler_class(**scaler_params)
                    #             transformed = scaler.fit_transform(transformed.reshape(-1, 1)).flatten()

                    #         region_df[f"{media_var}_transformed"] = transformed
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
                            region_df[f"{var}_contribution"] = beta_value * region_df[f"scaled_{var}"]
                            

                    transformed_data_list.append(region_df)

                # Concatenate all transformed data
                transformed_df = pd.concat(transformed_data_list, axis=0).reset_index(drop=True)
                return transformed_df
            
            # # Create a session state variable for storing the selected model
            # if "selected_model" not in st.session_state:
            #     st.session_state.selected_model = None
            # filtered_model_results
            for _, row in filtered_model_results.iterrows():
                    region = row["Region"]
                    model_num = row["Model_num"]
                    uni_id = row["Unique_ID"]
                    approach = row["Approach"]
                    unique_key = f"plot{uni_id}_{approach}"

                    # # Model Selection Button
                    # if st.button(f"Select Model ID: {uni_id} and Approach: {approach}"):
                    #     st.session_state.selected_model = row.to_frame().T  # Store selected model

                    filtered_model_result = pd.DataFrame([row])  # Convert row to DataFrame to keep row structure

                    region_row = filtered_model_result[filtered_model_result["Region"] == region].iloc[0]

                    if 'Power' in M0.columns:
                        # Parse parameters into lists
                        power = list(map(float, region_row["Power"].split(',')))
                        carryovers = list(map(float, region_row["Carryover"].split(',')))
                        # Use uniform parameters for all media variables
                        uniform_power = power[0]
                        uniform_carryover = carryovers[0]

                        region_mape = region_row["Region_MAPEs"]
                        rsq = region_row["R_squared"]

                        st.write(f"#### Power: {uniform_power}, Carryover: {uniform_carryover}, Model MAPE: {region_mape:.2%}, R_sq: {rsq:.2}")
                    else:
                        # Parse parameters into lists
                        growth_rates = list(map(float, region_row["Growth_rate"].split(',')))
                        carryovers = list(map(float, region_row["Carryover"].split(',')))
                        mid_points = list(map(float, region_row["Mid_point"].split(',')))
                        # Use uniform parameters for all media variables
                        uniform_growth_rate = growth_rates[0]
                        uniform_carryover = carryovers[0]
                        uniform_midpoint = mid_points[0]

                        # region_mape = region_row["Region_MAPEs"]
                        # rsq = region_row["R_squared"]

                        # st.write(f"#### Growth rate: {uniform_growth_rate}, Carryover: {uniform_carryover}, Model MAPE: {region_mape:.2%}, R_sq: {rsq:.2}")
                    
                    # expanded_region_df
                    transformed_df = apply_transformations_with_contributions(filtered_data, filtered_model_result)

                
                    # Extract media and other variables dynamically
                    mainmedia_variables = [col.replace('_adjusted', '') for col in filtered_model_result.columns if col.endswith('_adjusted') and "Total" in col]
                    mediagenre_variables = [col.replace('_adjusted', '') for col in filtered_model_result.columns if col.endswith('_adjusted') and "Total" not in col]
                    other_variables = [col.replace('beta_scaled_', '') for col in filtered_model_result.columns if col.startswith('beta_scaled_')]

                    # Combine all variable names used in the model
                    mainmedia_model_variables = mainmedia_variables + other_variables
                    mediagenre_model_variables = mediagenre_variables + other_variables
                    # mediagenre_model_variables

                    # Identify contribution columns matching the model variables
                    mainmedia_contribution_columns = [
                        col for col in transformed_df.columns
                        if any(col.startswith(var) and col.endswith("_contribution") for var in mainmedia_model_variables)
                    ]
                    # contribution_columns
                    mediagenre_contribution_columns = [
                        col for col in transformed_df.columns
                        if any(col.startswith(var) and col.endswith("_contribution") for var in mediagenre_model_variables)
                    ]

                    # Compute MainMedia_predY dynamically
                    transformed_df["MainMedia_predY"] = transformed_df["beta0"] + transformed_df[mainmedia_contribution_columns].sum(axis=1)

                    # region_row["Y"]

                    # transformed_df["MainMedia_MAPE"] = abs(transformed_df["Filtered Volume Index"] - transformed_df["MainMedia_predY"])/transformed_df["Filtered Volume Index"]
                    # Get the Y variable name dynamically
                    y_variable = region_row["Y"]  # Assuming this stores the column name of Y

                    # Compute MainMedia_MAPE dynamically
                    transformed_df["MainMedia_MAPE"] = abs(transformed_df[y_variable] - transformed_df["MainMedia_predY"]) / transformed_df[y_variable]


                    transformed_df["Mediagenre_predY"] = transformed_df["beta0"] + transformed_df[mediagenre_contribution_columns].sum(axis=1)

                    transformed_df["Mediagenre_MAPE"] = abs(transformed_df[y_variable] - transformed_df["Mediagenre_predY"])/transformed_df[y_variable]
                    
                    # Plot Actual vs Predicted
                    date_values = transformed_df['Date']
                    actual_values = transformed_df[y_variable]
                    mainmedia_pred_values = transformed_df['MainMedia_predY']
                    mediagenre_pred_values = transformed_df['Mediagenre_predY']

                    # Calculate average MAPE
                    mainmedia_mape = transformed_df["MainMedia_MAPE"].mean()
                    mediagenre_mape = transformed_df["Mediagenre_MAPE"].mean()

                    model_type = row["Model_type"]
                    approach = row["Approach"]

                    fig = go.Figure()
                    fig.add_trace(go.Scatter(x=date_values, y=actual_values, mode='lines+markers', name='Actual Volume'))
                    fig.add_trace(go.Scatter(x=date_values, y=mainmedia_pred_values, mode='lines+markers', name=f'MainMedia PredY (MAPE: {mainmedia_mape:.2%})'))
                    fig.add_trace(go.Scatter(x=date_values, y=mediagenre_pred_values, mode='lines+markers', name=f'Mediagenre PredY (MAPE: {mediagenre_mape:.2%})'))


                    fig.update_layout(title=f'Actual vs Predicted Volume: {model_type} - {approach}',
                                    xaxis_title='Date',
                                    yaxis_title='Volume',
                                    legend_title='Legend')

                    st.plotly_chart(fig, use_container_width=True, key=f"plot_{uni_id}_{approach}_actual_vs_predicted")

                    ########################################################### Contribution main media Level #####################################################################

                    # Get the Y variable name dynamically
                    y_variable = region_row["Y"]  # Assuming this stores the column name of Y

                    # Identify contribution columns dynamically (all columns ending with '_contribution')
                    contribution_columns = [col for col in transformed_df.columns if col.endswith("_contribution")]

                    # Define the base columns that should always be included
                    base_columns = ["beta0", "MainMedia_predY", "Mediagenre_predY", y_variable]

                    # Create the aggregation dictionary dynamically
                    agg_dict = {col: "sum" for col in base_columns + contribution_columns}

                    # Group by Region and aggregate dynamically
                    contribution = transformed_df.groupby("Region").agg(agg_dict).reset_index()
                    # contribution.columns

                    # Extract contribution columns for mainmedia_model_variables
                    mainmedia_contribution_columns = [
                        col for col in contribution.columns if any(col.startswith(var) and col.endswith("_contribution") for var in mainmedia_model_variables)
                    ]
                    # mainmedia_model_variables

                    # mainmedia_contribution_columns

                    # Compute percentage contribution for each mainmedia contribution variable
                    for col in mainmedia_contribution_columns:
                        percentage_col = col.replace("_contribution", "_percentage")
                        contribution[percentage_col] = (contribution[col] / contribution["MainMedia_predY"]) * 100

                    # Compute base percentage separately
                    contribution["beta0_per"] = contribution["beta0"] / contribution["MainMedia_predY"] * 100

                    # Calculate Base percentage
                    contribution["Base_percentage"] = (
                        contribution["beta0_per"]
                    )

                    # Dynamically extract all percentage columns
                    mainmedia_percentage_columns = [col.replace("_contribution", "_percentage") for col in mainmedia_contribution_columns]
                    # mainmedia_contribution_columns
                    
                    # Columns to plot
                    # plot_columns = ["Base_percentage"] + mainmedia_percentage_columns
                    # Dynamically extract percentage contribution columns
                    plot_columns = [col for col in contribution.columns if col.endswith("_percentage")]
                    # st.dataframe(contribution

                    # Filter data based on selection
                    data = contribution

                    if not data.empty:
                        # Bar chart data
                        values = data[plot_columns].values.flatten()
                        # labels = ["Other Factors", "TV Reach", "Digital Reach","D1","Price","A&P","Seasonality"]
                        # # Dynamically extract percentage contribution columns
                        # plot_columns = [col for col in contribution.columns if col.endswith("_percentage")]

                        # Generate labels dynamically by cleaning column names
                        labels = [col.replace("_percentage", "").replace("_", " ").title() for col in plot_columns]

                        # Create Plotly Bar Chart with Custom Styling
                        fig = px.bar(
                            x=labels,
                            y=values,
                            text=values,  # Display values on bars
                            title=f"Contribution {model_type} - {approach}",
                            color=labels,  # Use color to distinguish categories
                            color_discrete_sequence=px.colors.sequential.Purp
                        )

                        # Customize the text and layout
                        fig.update_traces(
                            texttemplate='%{text:.2f}%',  # Format text values
                            textposition='outside',  # Position text above bars
                        )

                        # Find min and max y-values
                        y_max = max(values)
                        y_min = min(values)

                        # Extend range slightly for better visibility
                        y_buffer = (y_max - y_min) * 0.12
                        # 10% padding

                        fig.update_layout(
                            title_font_size=15,
                            title_font_family="Arial",
                            title_x=0.001,  # Center-align title
                            yaxis_range=[y_min - y_buffer, y_max + y_buffer],  # Dynamically set y-axis limits
                            showlegend=False,  # Hide legend
                            margin=dict(l=40, r=40, t=100, b=40),  # Margins for better spacing
                            height=400,  # Suitable height for bar chart
                            yaxis_title="Percentage Contribution"  # Add y-axis title for clarity
                        )

                        # Show the chart in Streamlit
                        st.plotly_chart(fig, use_container_width=True, key=f"plot_{uni_id}_{approach}_contribution")
                    else:
                        st.warning(f"No data available for {model_type} - {approach}.")
                    
                    ########################################################### Contribution Genre Level #####################################################################


                    mediagenre_contribution_columns = [
                        col for col in contribution.columns if any(col.startswith(var) and col.endswith("_contribution") for var in mediagenre_contribution_columns)
                    ]

                    # mainmedia_contribution_columns

                    # Compute percentage contribution for each mainmedia contribution variable
                    for col in mediagenre_contribution_columns:
                        percentage_col = col.replace("_contribution", "_percentage_genre")
                        contribution[percentage_col] = (contribution[col] / contribution["Mediagenre_predY"]) * 100

                    # Compute base percentage separately
                    contribution["beta0_per_genre"] = contribution["beta0"] / contribution["Mediagenre_predY"] * 100

                    # Calculate Base percentage
                    contribution["Base_percentage_genre"] = (
                        contribution["beta0_per_genre"]
                    )

                    # Dynamically extract all percentage columns
                    mainmedia_percentage_columns = [col.replace("_contribution", "_percentage_genre") for col in mediagenre_contribution_columns]
                    # media_percentage_columns
                    
                    # Columns to plot
                    # plot_columns = ["Base_percentage"] + mainmedia_percentage_columns
                    # Dynamically extract percentage contribution columns
                    plot_columns = [col for col in contribution.columns if col.endswith("_percentage_genre")]
                    # st.dataframe(contribution

                    # Filter data based on selection
                    # data = contribution

                    # Filter data based on selection
                    data2 = contribution

                    if not filtered_data.empty:
                        # Bar chart data
                        values = data2[plot_columns].values.flatten()
                        # labels = ["Other Factors","D1","Price","A&P","Seasonality","TV Cricket","TV Movies","TV Music","TV Mews","TV GEC","Meta"," Dig Others","YT"]
                        labels = [col.replace("_percentage_genre", "").replace("_", " ").title() for col in plot_columns]

                        # Create Plotly Bar Chart with Custom Styling
                        fig = px.bar(
                            x=labels,
                            y=values,
                            text=values,  # Display values on bars
                            title=f"Contribution  {model_type} - {approach}",
                            color=labels,  # Use color to distinguish categories
                            color_discrete_sequence=px.colors.sequential.Purp
                        )

                        # Customize the text and layout
                        fig.update_traces(
                            texttemplate='%{text:.2f}%',  # Format text values
                            textposition='outside',  # Position text above bars
                        )

                        # Find min and max y-values
                        y_max = max(values)
                        y_min = min(values)

                        # Extend range slightly for better visibility
                        y_buffer = (y_max - y_min) * 0.12  # 10% padding

                        fig.update_layout(
                            title_font_size=15,
                            title_font_family="Arial",
                            title_x=0.001,  # Center-align title
                            showlegend=False,  # Hide legend
                            yaxis_range=[y_min - y_buffer, y_max + y_buffer],  # Dynamically set y-axis limits
                            margin=dict(l=40, r=40, t=100, b=40),  # Margins for better spacing
                            height=400,  # Suitable height for bar chart
                            yaxis_title="Percentage Contribution"  # Add y-axis title for clarity
                        )

                        # Show the chart in Streamlit
                        st.plotly_chart(fig, use_container_width=True, key=f"plot_{uni_id}_{approach}_contribution_genre")
                    else:
                        st.warning(f"No data available for {model_type} - {approach}.")

                    # Model Selection Button
                    if st.button(f"Select Model ID: {uni_id} - Approach: {approach}"):
                        selected_row_df = row.to_frame().T  # Convert row to DataFrame

                        # # Ensure no duplicate selection for the same region
                        # if not st.session_state.selected_models_df.empty:
                        #     existing_regions = st.session_state.selected_models_df["Region"].unique()
                        #     if selected_region in existing_regions:
                        #         st.session_state.selected_models_df = st.session_state.selected_models_df[st.session_state.selected_models_df["Region"] != selected_region]

                        # Ensure no duplicate selection for the same region
                        if not st.session_state.selected_models_df.empty:
                            existing_regions = st.session_state.selected_models_df["Region"].unique()
                            if selected_region in existing_regions:
                                st.session_state.selected_models_df = st.session_state.selected_models_df[st.session_state.selected_models_df["Region"] != selected_region]
                                # st.session_state.selected_models_df

                        # Append new selection
                        st.session_state.selected_models_df = pd.concat([st.session_state.selected_models_df, selected_row_df], ignore_index=True)
                        # st.dataframe(st.session_state.selected_models_df, use_container_width=True)

                    st.markdown(
                        """ 
                        <div style="height: 2px; background-color: black; margin: 10px 0;"></div>
                        """, 
                        unsafe_allow_html=True
                        )

        # Button to lock the selection
        # if st.button("Confirm Selection (No Further Changes)"):
        #     st.session_state.selection_locked = True  # Lock selection


        # with col6:
        #     # Button to lock the selection
        #     if st.button("Confirm Selection (No Further Changes)"):
        #         st.session_state.selection_locked = True  # Lock selection
        #     # Display Selected Models
        #     if not st.session_state.selected_models_df.empty:
        #         st.subheader("Selected Models Across Regions")
        #         st.write(st.session_state.selected_models_df)

        #     # final_selected_models_df = st.session_state.selected_models_df
        #     # final_selected_models_df
        #     # Only proceed with calculations if selection is locked
        #         if st.session_state.selection_locked:
        #             final_selected_models_df = st.session_state.selected_models_df
        #             st.write("Proceeding with calculations using the locked models...")

        #     # Extract unique regions from the selected models DataFrame
        #     selected_regions = final_selected_models_df["Region"].unique()
        # with col6:
        #     # # Button to lock the selection
        #     # if st.button("Confirm Selection (No Further Changes)", key="confirm_selection_button"):
        #     #     st.session_state.selection_locked = True  # Lock selection

        #     # Display Selected Models
        #     if not st.session_state.selected_models_df.empty:
        #         st.subheader("Selected Models Across Regions")
        #         st.write(st.session_state.selected_models_df)

        #         # Button to lock the selection
        #     if st.button("Confirm Selection (No Further Changes)", key="confirm_selection_button"):
        #         st.session_state.selection_locked = True  # Lock selection

        #         # Initialize final_selected_models_df to avoid NameError
        #         final_selected_models_df = st.session_state.selected_models_df if st.session_state.selection_locked else pd.DataFrame()

        #         if st.session_state.selection_locked:
        #             st.write("Proceeding with calculations using the locked models...")

        #         # Extract unique regions only if final_selected_models_df is not empty
        #         if not final_selected_models_df.empty:
        #             selected_regions = final_selected_models_df["Region"].unique()


        #     # Filter df to keep only rows corresponding to selected regions
        #     filtered_d1 = df[df["Region"].isin(selected_regions)]

        #     filtered_d1

        with col6:
            # Show selected models
            if not st.session_state.selected_models_df.empty:
                st.subheader("Selected Models Across Regions")
                st.write(st.session_state.selected_models_df)

            # Button to lock the selection
            if st.button("Confirm Selection (No Further Changes)", key="confirm_selection_button"):
                st.session_state.selection_locked = True  # Lock selection
                st.write("Proceeding with calculations using the locked models...")

            # Set a fallback in case nothing is selected
            final_selected_models_df = (
                st.session_state.selected_models_df if st.session_state.get("selection_locked") else pd.DataFrame()
            )

            selected_regions = final_selected_models_df["Region"].unique() if not final_selected_models_df.empty else []
            selected_brands = final_selected_models_df["Brand"].unique() if not final_selected_models_df.empty else []
            # selected_regions

            # Filter df to keep only rows corresponding to selected regions
            filtered_d1 = df[df["Region"].isin(selected_regions)]
            filtered_d1 = filtered_d1[filtered_d1["Brand"].isin(selected_brands)]  # Filter by selected brands
            # filtered_d1


            


            st.write("### Cluster Beta Calculation")
            import numpy as np
            from sklearn.preprocessing import MinMaxScaler, StandardScaler

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

            def apply_transformations_with_contributions2(df, region_weight_df):
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
                unique_regions = df["Region"].unique()

                # region_weight_df.columns

                # Extract media variables dynamically
                media_variables = [
                    col.replace('_adjusted', '')
                    for col in region_weight_df.columns
                    if col.endswith('_adjusted') 
                ]

                # Extract other variables dynamically
                other_variables = [
                    col.replace('beta_scaled_', '')
                    for col in region_weight_df.columns
                    if col.startswith('beta_scaled_')
                ]
                # other_variables

                # Include beta0 in the calculations
                if 'beta0' in region_weight_df.columns:
                    include_beta0 = True
                else:
                    include_beta0 = False

                # # Add additional media variables
                # additional_media_vars = ['TV_Total_Unique_Reach', 'Digital_Total_Unique_Reach']
                # media_variables += additional_media_vars

                # Filter data by Region and Brand
                filtered_data = {
                region: df[df["Region"] == region].copy() for region in unique_regions
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

                    # Transformation parameters for each media variable
                    # carryovers = [0.8] * len(media_variables)  # Example: Set 0.5 for all media variables
                    # growth_rates = [3.5] * len(media_variables)  # Example: Set 3.5 for all media variables
                    # mid_points = [0.0] * len(media_variables)  # Example: Set 0.0 for all media variables

                    # # Extract Growth Rate, Carryover, and Midpoint from region_row
                    # growth_rates = region_row["Growth_rate"]
                    # carryovers = region_row["Carryover"]
                    # mid_points = region_row["Mid_point"]

                    # # Convert comma-separated string values into lists of floats
                    # growth_rates = list(map(float, growth_rates.split(',')))
                    # carryovers = list(map(float, carryovers.split(',')))
                    # mid_points = list(map(float, mid_points.split(',')))

                    # # Ensure all three lists are non-empty before using them
                    # if growth_rates and carryovers and mid_points:
                    #     if len(set(growth_rates)) == 1 and len(set(carryovers)) == 1 and len(set(mid_points)) == 1:
                    #         growth_rates = [growth_rates[0]] * len(media_variables)
                    #         carryovers = [carryovers[0]] * len(media_variables)
                    #         mid_points = [mid_points[0]] * len(media_variables)
                    # else:
                    #     raise ValueError("One or more required columns (Growth_rate, Carryover, Mid_point) are missing or empty in region_row.")
                    # Fetch transformation type
                    transformation_type = region_row.get("Transformation_type", "logistic")

                    # --- Handle transformation-specific parameters ---
                    if transformation_type == "logistic":
                        growth_rates = list(map(float, str(region_row.get("Growth_rate", "")).split(',')))
                        carryovers = list(map(float, str(region_row.get("Carryover", "")).split(',')))
                        mid_points = list(map(float, str(region_row.get("Mid_point", "")).split(',')))

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

                    # standardization_method = 'minmax'

                    # if region_weight_df["standardization_method"] == 'minmax':
                    #     scaler_class = MinMaxScaler
                    #     scaler_params = {'feature_range': (0, 1)}
                    # elif region_weight_df["standardization_method"] == 'zscore':
                    #     scaler_class = StandardScaler
                    #     scaler_params = {}
                    # elif region_weight_df["standardization_method"] == 'none':
                    #     scaler_class = None
                    # else:
                    #     raise ValueError(f"Unsupported standardization method: {region_weight_df["standardization_method"]}")

                    # Ensure column exists before accessing
                    if "Standardization_method" not in region_weight_df.columns:
                        raise KeyError("The column 'Standardization_method' is missing in region_weight_df.")

                    # Access the standardization method for the current region
                    standardization_method = region_row["Standardization_method"]

                    if standardization_method == 'minmax':
                        scaler_class = MinMaxScaler
                        scaler_params = {'feature_range': (0, 1)}
                    elif standardization_method == 'zscore':
                        scaler_class = StandardScaler
                        scaler_params = {}
                    elif standardization_method == 'none':
                        scaler_class = None
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

                    # # Transform media variables and calculate contributions
                    # for idx, media_var in enumerate(media_variables):
                    #     if media_var in region_df.columns:
                    #         growth_rate = growth_rates[idx]
                    #         carryover = carryovers[idx]
                    #         mid_point = mid_points[idx]
                    #         beta_col = f"{media_var}_adjusted"

                    #         adstocked = adstock_function(region_df[media_var].values, carryover)
                    #         standardized = (adstocked - np.mean(adstocked)) / np.std(adstocked)
                    #         transformed = logistic_function(standardized, growth_rate, mid_point)
                    #         transformed = np.nan_to_num(transformed)

                    #         if scaler_class:
                    #             scaler = scaler_class(**scaler_params)
                    #             transformed = scaler.fit_transform(transformed.reshape(-1, 1)).flatten()

                    #         region_df[f"{media_var}_transformed"] = transformed

                    #         # Calculate contribution if beta is available
                    #         if beta_col in region_row:
                    #             beta_value = float(region_row[beta_col])
                    #             region_df[f"{media_var}_contribution"] = beta_value * transformed
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
                            region_df[f"{var}_contribution"] = beta_value * region_df[f"scaled_{var}"]
                            

                    transformed_data_list.append(region_df)

                # Concatenate all transformed data
                transformed_df = pd.concat(transformed_data_list, axis=0).reset_index(drop=True)
                return transformed_df

            if not final_selected_models_df.empty:
                # Apply transformations with contributions
                transformed_df2 = apply_transformations_with_contributions2(filtered_d1, final_selected_models_df)
                transformed_df2 = transformed_df2.fillna(0)  
            # transformed_df2
            # media_prefixes = [col.split('_')[0] for col in media_variable]  
            # media_prefixes = list(set(media_prefixes))  # Unique prefixes for media vehicles

            # st.dataframe(transformed_df2) 

            import pandas as pd
            import numpy as np

            # Function to apply adstock transformation
            def adstock(data, feature, carryover_effect):
                if data["Market"].nunique() == 1:
                    result = [0] * len(data)
                    for i in range(len(data)):
                        if i == 0:
                            result[0] = data[feature].iloc[0]
                        else:
                            result[i] = data[feature].iloc[i] + carryover_effect * result[i - 1]
                    data[feature] = result
                else:
                    raise ValueError("Market is not unique! Please check the data.")
                return data

            def maxmin_scaler(data, feature, market):
                max = data[feature].max()
                min = data[feature].min()
                if max == min:
                    print(f"Warning: The range of '{feature}' is zero for {market}. Assigning NAN to the standardized column.")
                    data["scaled_"+feature] = np.nan
                else:
                    data["scaled_"+feature] = (data[feature] - min) / (max - min)
                return data

            # Function to standardize the data
            def standardize(data, feature, market):
                if data["Market"].nunique() == 1:
                    mean = data[feature].mean()
                    std = data[feature].std()
                    if std == 0:
                        print(f"Warning: The standard deviation of '{feature}' is zero for {market}. Assigning NAN to the standardized column.")
                        data[feature + "_standardized"] = np.nan
                    else:
                        data[feature + "_standardized"] = (data[feature] - mean) / std
                else:
                    raise ValueError("Market is not unique! Please check the data.")
                return data



            # Logistic sigmoid function
            def logistic_sigmoid(x, growth_rate, mid_point):
                return 1 / (1 + np.exp(-growth_rate * (x - mid_point)))

            # Transformation function
            if 'Power' in final_selected_models_df.columns:
                def transformation(data, coef_df, feature, market, carryover_effect, power):
                    # power
                    data = adstock(data, feature, carryover_effect)
                    data = standardize(data, feature, market)  # Fix this line to include the market argument
                    data[feature + "_power"] = np.power(data[feature + "_standardized"], power)
                    return data
            else:
                def transformation(data, coef_df,  feature, market, carryover_effect, growth_rate, mid_point):
                    data = adstock(data, feature, carryover_effect)
                    data = standardize(data, feature, market)  # Fix this line to include the market argument
                    data[feature + "_logistic"] = logistic_sigmoid(data[feature + "_standardized"], growth_rate, mid_point)
                    return data

            # Function to process markets
            if 'Power' in final_selected_models_df.columns:
                def process_markets1(data, coef_df, features, other_variables, carryover_effect, power):
                    all_market_data = []
                    mean_trch_pred = []
                    mean_trch = []
                    volume_mean = []

                    # Lists to store data for the new DataFrames
                    other_variables_data = []
                    media_variables_data = []

                    for market in data["Region"].unique():
                        market_data = data[data["Region"] == market].reset_index(drop=True)
                        volume = market_data["Volume"].mean()
                        volume_mean.append(volume)

                        # For other variables
                        for variable in other_variables:
                            market_data = maxmin_scaler(market_data, variable, market)
                            # Correcting the standardized column name
                            variable_mean = market_data["scaled_"+variable].mean()
                            coef_var = coef_df[coef_df["Region"] == market]["beta_scaled_" + variable].values[0]
                            var_con = coef_var * volume * variable_mean
                            other_variables_data.append({"Region": market, "Variable": variable, "Beta": var_con})

                        # For media variables
                        for media_variable in features:
                            # carryover_effect[0]
                            # if "TV" in media_variable:
                            #     market_data = transformation(market_data, coef_df,  media_variable, market, carryover_effect[0], power)
                            # else:
                            #     market_data = transformation(market_data, coef_df, media_variable, market, carryover_effect[1], power)

                            market_data = transformation(market_data, coef_df, media_variable, market, carryover_effect, power)

                            market_data = maxmin_scaler(market_data, media_variable + "_power", market)
                            mean_transform_reach = market_data["scaled_"+media_variable + "_power"].mean()
                            coef = coef_df[coef_df["Region"] == market][media_variable + "_adjusted"].values[0]
                            rch_pred = mean_transform_reach * coef * volume
                            mean_trch_pred.append(rch_pred)
                            mean_trch.append(mean_transform_reach)
                            media_variables_data.append({
                                "Region": market,
                                "Media_Variable": media_variable,
                                "Beta": rch_pred})
                    
                        all_market_data.append(market_data)

                    # Create DataFrames for other variables and media variables
                    other_variables_df = pd.DataFrame(other_variables_data)
                    media_variables_df = pd.DataFrame(media_variables_data)

                    return (
                        pd.concat(all_market_data, ignore_index=True),
                        mean_trch,
                        mean_trch_pred,
                        volume_mean,
                        other_variables_df,
                        media_variables_df
                    )
            else:
                def process_markets1(data, coef_df, features, other_variables, carryover_effect, growth_rate, mid_point):
                    all_market_data = []
                    mean_trch_pred = []
                    mean_trch = []
                    volume_mean = []

                    # Lists to store data for the new DataFrames
                    other_variables_data = []
                    media_variables_data = []

                    for market in data["Region"].unique():
                        market_data = data[data["Region"] == market].reset_index(drop=True)
                        volume = market_data["Volume"].mean()
                        volume_mean.append(volume)

                        # For other variables
                        for variable in other_variables:
                            market_data = maxmin_scaler(market_data, variable, market)
                            # Correcting the standardized column name
                            variable_mean = market_data["scaled_"+variable].mean()
                            coef_var = coef_df[coef_df["Region"] == market]["beta_scaled_" + variable].values[0]
                            var_con = coef_var * volume * variable_mean
                            other_variables_data.append({"Region": market, "Variable": variable, "Beta": var_con})

                        # For media variables
                        for media_variable in features:
                            # if "TV" in media_variable:
                            #     market_data = transformation(market_data, coef_df,  media_variable, market, carryover_effect[0], growth_rate, mid_point)
                            # else:
                            #     market_data = transformation(market_data, coef_df, media_variable, market, carryover_effect[1], growth_rate, mid_point)
                            
                            market_data = transformation(market_data, coef_df,  media_variable, market, carryover_effect, growth_rate, mid_point)

                            market_data = maxmin_scaler(market_data, media_variable + "_logistic", market)
                            mean_transform_reach = market_data["scaled_"+media_variable + "_logistic"].mean()
                            coef = coef_df[coef_df["Region"] == market][media_variable + "_adjusted"].values[0]
                            rch_pred = mean_transform_reach * coef * volume
                            mean_trch_pred.append(rch_pred)
                            mean_trch.append(mean_transform_reach)
                            media_variables_data.append({
                                "Region": market,
                                "Media_Variable": media_variable,
                                "Beta": rch_pred})

                        all_market_data.append(market_data)

                    # Create DataFrames for other variables and media variables
                    other_variables_df = pd.DataFrame(other_variables_data)
                    media_variables_df = pd.DataFrame(media_variables_data)

                    return (
                        pd.concat(all_market_data, ignore_index=True),
                        mean_trch,
                        mean_trch_pred,
                        volume_mean,
                        other_variables_df,
                        media_variables_df
                    )
                
            if not final_selected_models_df.empty:
            
                ## required data for function
                data3 = transformed_df2.copy()
                coef_df = final_selected_models_df.copy()
                # media_variable = ['Digital_Meta_All_Reach', 'Digital_Others_All_Reach','Digital_Youtube_All_Reach',
                #        'TV_Cricket_All_Reach', 'TV_Movies_All_Reach', 'TV_Music_All_Reach',
                #        'TV_News_All_Reach', 'TV_Others_All_Reach']

                # Extract media variables dynamically
                # media_variable = [
                #         col.replace("_adjusted", "") for col in coef_df
                #         if any(prefix in col for prefix in ["Digital_", "TV_"]) and "Total" not in col
                #     ]
                media_variable = [
                    col.replace("_adjusted", "") 
                    for col in coef_df 
                    if col.endswith("_adjusted") and "Total" not in col
                ]
                # media_variable

                # Extract other variables dynamically
                other_variables = [
                    col.replace('beta_', '').replace('scaled_', '')
                    for col in coef_df.columns
                    if col.startswith('beta_') and 'scaled_' in col
                ]

                # media_variable = ['Digital_Meta_Unique_Reach', 'Digital_Others_Unique_Reach',
                #         'Digital_Youtube_Unique_Reach',
                #     'TV_Cricket_Unique_Reach', 'TV_Movies_Unique_Reach',
                #     'TV_Music_Unique_Reach', 'TV_News_Unique_Reach',
                #     'TV_Others_Unique_Reach']

                # other_variables = ['D1', 'Price', 'Region_Brand_seasonality', 'A&P_Amount_Spent']

                # carryover_effect_tv = 0.8
                # carryover_effect_digital = 0.8
                # carryover_effect = [carryover_effect_tv, carryover_effect_digital]
                # growth_rate = 3.5
                # mid_point = 0
                # Assume you have a consistent media order
                media_prefixes = [col.split('_')[0] for col in media_variable]  
                media_prefixes = list(set(media_prefixes))  # Unique prefixes for media vehicles
                # media_prefixes
                # Extract Growth Rate, Carryover, and Midpoint from region_row
                if 'Power' in final_selected_models_df.columns:
                    carryover_effect = list(map(float, coef_df["Carryover"][0].split(',')))
                    power = list(map(float, coef_df["Power"][0].split(',')))

                    # # Assign single values if all elements in the list are the same
                    carryover_effect = carryover_effect[0] if len(set(carryover_effect)) == 1 else carryover_effect
                    # carryover_effect
                    power = power[0] if len(set(power)) == 1 else power
                    # Handle single values
                    # if len(set(carryover_effect)) == 1:
                    #     carryover_effect = {prefix: carryover_effect[0] for prefix in media_prefixes}
                    # else:
                    #     carryover_effect = {prefix: val for prefix, val in zip(media_prefixes, carryover_effect)}

                    # if len(set(power)) == 1:
                    #     power = {prefix: power[0] for prefix in media_prefixes}
                    # else:
                    #     power = {prefix: val for prefix, val in zip(media_prefixes, power)}
                    # carryover_effect

                else:
                    growth_rates = list(map(float, coef_df["Growth_rate"][0].split(',')))
                    carryovers = list(map(float, coef_df["Carryover"][0].split(',')))
                    mid_points = list(map(float, coef_df["Mid_point"][0].split(',')))

                    # Assign single values if all elements in the list are the same
                    growth_rate = growth_rates[0] if len(set(growth_rates)) == 1 else growth_rates
                    carryover_effect = carryovers[0] if len(set(carryovers)) == 1 else carryovers
                    mid_point = mid_points[0] if len(set(mid_points)) == 1 else mid_points

                # Split carryover into TV and Digital
                # carryover_effect_tv = carryover_effect if isinstance(carryover_effect, float) else carryover_effect[0]
                # carryover_effect_digital = carryover_effect if isinstance(carryover_effect, float) else carryover_effect[1]
                # carryover_effect = [carryover_effect_tv, carryover_effect_digital]
                # carryover_effect

                # st.write(media_variable,other_variables,growth_rate,carryover_effect,mid_point,carryover_effect_digital,carryover_effect_tv)

                if 'Power' in final_selected_models_df.columns:
                    # Call the function with power transformation
                    market_data, mean_trch, mean_trch_pred, volume_mean, other_variables_df, media_variables_df = process_markets1(data3, coef_df, media_variable, other_variables, carryover_effect, power)
                else:
                    market_data, mean_trch, mean_trch_pred, volume_mean, other_variables_df, media_variables_df = process_markets1(data3, coef_df, media_variable, other_variables, carryover_effect, growth_rate, mid_point)

                market_data = market_data.fillna(0)

                grouped_media_variables_df = media_variables_df.groupby("Media_Variable", as_index=False).agg({"Beta": "sum"})
                # media_variables_df
                grouped_other_variables_df = other_variables_df.groupby("Variable", as_index=False).agg({"Beta": "sum"})

                if "KPI" in df.columns:
                    # Convert Year column to string
                    df['Year'] = df['Year'].astype(str)
                    transformed_df_all = df.groupby(['Market', 'Brand', 'Year', 'Month'], as_index=False).agg(
                        {**{col: 'sum' for col in df.select_dtypes(include='number').columns if col not in ["D1","KPI"]},
                        'D1': 'sum',
                        "KPI": 'mean'}
                    ).reset_index(drop=True)
                    transformed_df_all["Price"] = transformed_df_all["Sales"]/transformed_df_all["Volume"]
                else:
                    # Convert Year column to string
                    df['Year'] = df['Year'].astype(str)
                    transformed_df_all = df.groupby(['Market', 'Brand', 'Year', 'Month'], as_index=False).agg(
                        {**{col: 'sum' for col in df.select_dtypes(include='number').columns if col not in ['Channel', 'Variant', 'PackType', 'PPG', 'PackSize', 'Week',"D1"]},
                        'D1': 'sum'}
                    ).reset_index()
                    transformed_df_all["Price"] = transformed_df_all["Sales"]/transformed_df_all["Volume"]

                transformed_df_all = transformed_df_all.drop(columns="index")
                # transformed_df_all

                month_order = {
                "January": 1, "February": 2, "March": 3, "April": 4, "May": 5, "June": 6,
                "July": 7, "August": 8, "September": 9, "October": 10, "November": 11, "December": 12
                }

                transformed_df_all["Month_Num"] = transformed_df_all["Month"].map(month_order)
                transformed_df_all = transformed_df_all.sort_values(by=["Year", "Month_Num"], ascending=[True, True])
                transformed_df_all = transformed_df_all.drop(columns=["Month_Num"])

                variable_mean_for_pred = []
                original_mean = []
                for index, row in grouped_other_variables_df.iterrows():
                    variable_name = row["Variable"]
                    # Check if the variable exists in df
                    if variable_name in transformed_df_all.columns:
                        # Calculate the mean of the variable in df
                        print(variable_name)
                        transformed_df_all[variable_name+"_transformed"] = ((transformed_df_all[variable_name] - transformed_df_all[variable_name].min())/(transformed_df_all[variable_name].max() - transformed_df_all[variable_name].min()))
                        variable_mean_pred = (transformed_df_all[variable_name+"_transformed"].mean())*np.sum(volume_mean)
                        variable_mean = transformed_df_all[variable_name+"_transformed"].mean()
                        variable_mean_for_pred.append(variable_mean)
                        original_mean.append(transformed_df_all[variable_name].mean())

                        if variable_mean != 0:
                            grouped_other_variables_df.loc[index, "Beta"] /= variable_mean_pred
                        else:
                            print(f"Warning: Mean of {variable_name} is zero. Skipping division.")
                    else:
                        print(f"Warning: {variable_name} not found in df columns. Skipping.")

                grouped_other_variables_df["transformed_mean"]  = variable_mean_for_pred
                grouped_other_variables_df["original_mean"]  = original_mean
                # grouped_media_variables_df

                grouped_other_variables_df["Pred"] = grouped_other_variables_df["Beta"] * grouped_other_variables_df["transformed_mean"]
                # grouped_other_variables_df

                grouped_media_variables_df["Beta"]  = grouped_media_variables_df["Beta"]/(np.sum(volume_mean))

                import pandas as pd
                import numpy as np

                def adstock(data, feature, carryover_effect):
                    result = [0] * len(data)
                    for i in range(len(data)):
                        if i == 0:
                            result[0] = data[feature].iloc[0]
                        else:
                            result[i] = data[feature].iloc[i] + carryover_effect * result[i - 1]
                    data[feature] = result
                    return data


                def maxmin_scaler(data, feature):
                    max = data[feature].max()
                    min = data[feature].min()
                    if max == min:
                        print(f"Warning: The range of '{feature}' is zero for. Assigning NAN to the standardized column.")
                        data["scaled_"+feature] = np.nan
                    else:
                        data["scaled_"+feature] = (data[feature] - min) / (max - min)
                    return data


                def standardize(data, feature):
                    mean = data[feature].mean()
                    std = data[feature].std()
                    if std == 0:
                        print(f"Warning: The standard deviation of '{feature}' is zero. Assigning NAN to the standardized column.")
                        data[feature + "_standardized"] = np.nan
                    else:
                        data[feature + "_standardized"] = (data[feature] - mean) / std
                    return data, mean, std


                # Logistic sigmoid function
                def logistic_sigmoid(x, growth_rate, mid_point):
                    return 1 / (1 + np.exp(-growth_rate * (x - mid_point)))
                
                if 'Power' in final_selected_models_df.columns:
                    def media_transformation(data, features, carryover_effect, power):
                        for feature in features:
                            data = adstock(data, feature, carryover_effect)
                            data, mean, std = standardize(data, feature)
                            data[feature + "_power_transformation"] = np.power(data[feature + "_standardized"], power)
                            data["scaled_" + feature + "_power_transformation"] = (data[feature + "_power_transformation"] - data[feature + "_power_transformation"].min()) / (data[feature + "_power_transformation"].max() - data[feature + "_power_transformation"].min())
                        return data
                else:
                    def media_transformation(data, features, carryover_effect, growth_rate, mid_point):
                        for feature in features:
                            data = adstock(data, feature, carryover_effect)
                            data, mean, std = standardize(data, feature)
                            data[feature + "_logistic_transformation"] = logistic_sigmoid(data[feature + "_standardized"], growth_rate, mid_point)
                            data["scaled_" + feature + "_logistic_transformation"] = (data[feature + "_logistic_transformation"] - data[feature + "_logistic_transformation"].min()) / (data[feature + "_logistic_transformation"].max() - data[feature + "_logistic_transformation"].min())
                        return data


                data_all = transformed_df_all.copy()

                # media_variable = [
                #         col.replace("_adjusted", "") for col in coef_df
                #         if any(prefix in col for prefix in ["Digital_", "TV_"]) or "Total" in col
                #     ]
                # media_variable
                media_variable = [
                    col.replace("_adjusted", "") 
                    for col in coef_df 
                    if col.endswith("_adjusted") or "Total" in col
                ]

                if 'Power' in final_selected_models_df.columns:
                    # Extract Carryover from region_row
                    carryovers = list(map(float, coef_df["Carryover"][0].split(',')))
                    power = list(map(float, coef_df["Power"][0].split(',')))

                    # Assign single values if all elements in the list are the same
                    carryover_effect = carryovers[0] if len(set(carryovers)) == 1 else carryovers
                    power = power[0] if len(set(power)) == 1 else power
                else:
                    # Extract Growth Rate, Carryover, and Midpoint from region_row
                    growth_rates = list(map(float, coef_df["Growth_rate"][0].split(',')))
                    carryovers = list(map(float, coef_df["Carryover"][0].split(',')))
                    mid_points = list(map(float, coef_df["Mid_point"][0].split(',')))

                    # Assign single values if all elements in the list are the same
                    growth_rate = growth_rates[0] if len(set(growth_rates)) == 1 else growth_rates
                    carryover_effect = carryovers[0] if len(set(carryovers)) == 1 else carryovers
                    mid_point = mid_points[0] if len(set(mid_points)) == 1 else mid_points

                # st.write(growth_rate,carryover_effect,mid_point)

                if 'Power' in final_selected_models_df.columns:
                    data_media = media_transformation(data_all, media_variable, carryover_effect, power)
                else:

                    data_media = media_transformation(data_all, media_variable, carryover_effect, growth_rate, mid_point)

                transformed_mean_list = []
                original_mean_list = []
                for index, row in grouped_media_variables_df.iterrows():
                    media_variable_name = row["Media_Variable"]
                    if 'Power' in final_selected_models_df.columns:
                        # Construct the corresponding column name in the data DataFrame
                        transformed_column_name = "scaled_" + media_variable_name + "_power_transformation"
                    else:
                        # Construct the corresponding column name in the data DataFrame
                        transformed_column_name = "scaled_" + media_variable_name + "_logistic_transformation"

                    # Check if the column exists in the data DataFrame
                    if transformed_column_name in data_media.columns:
                        # Calculate the mean of the transformed column
                        transformed_mean = data_media[transformed_column_name].mean()
                        transformed_mean_list.append(transformed_mean)
                        original_mean_list.append(transformed_df[media_variable_name].mean())

                        # Avoid division by zero
                        if transformed_mean != 0:
                            # Update the Reach_Pred value by dividing it by the mean
                            grouped_media_variables_df.loc[index, "Beta"] /= transformed_mean
                        else:
                            print(f"Warning: Mean of {transformed_column_name} is zero. Skipping division.")
                    else:
                        print(f"Warning: {transformed_column_name} not found in data columns. Skipping.")

                grouped_media_variables_df["transformed_mean"] = transformed_mean_list
                grouped_media_variables_df["original_mean"] = original_mean_list

                grouped_media_variables_df.rename(columns={'Media_Variable': 'Variable', 'Reach_Pred': 'Var_Con'}, inplace=True)
                # grouped_media_variables_df

                intercept = np.array(final_selected_models_df["beta0"])
                # intercept

                intercept = np.array(final_selected_models_df["beta0"])
                sum = 0
                for i in range(len(intercept)) :
                    array = intercept[i] * volume_mean[i]
                    sum = sum + array
                inter = sum/np.sum(volume_mean)
                # inter

                # grouped_media_variables_df_digital = grouped_media_variables_df[grouped_media_variables_df['Variable'].str.startswith("Digital")].reset_index(drop=True)
                # grouped_media_variables_df_tv = grouped_media_variables_df[grouped_media_variables_df['Variable'].str.startswith("TV")].reset_index(drop=True)

                # final_coef_df = pd.concat([grouped_other_variables_df, grouped_media_variables_df], ignore_index=True)
                # final_coef_df["Variable"] = final_coef_df["Variable"].apply(lambda x: x + "_adjusted" if x.startswith(("TV", "Digital")) else "beta_scaled_" + x)
                # # final_coef_df

                # # Extract Digital and TV variables dynamically from coef_df
                # digital_vars = [col.replace("_adjusted", "") for col in coef_df if "Digital_" in col and "Total" not in col]
                # tv_vars = [col.replace("_adjusted", "") for col in coef_df if "TV_" in col and "Total" not in col]
                # # tv_vars

                # # Filter digital variables
                # grouped_media_variables_df_digital_uni = grouped_media_variables_df_digital[
                #     grouped_media_variables_df_digital["Variable"].isin(digital_vars)
                # ]

                # mainmedia_variables = [col.replace('_adjusted', '') for col in filtered_model_result.columns if col.endswith('_adjusted') and "Total" in col]
                # # [f"scaled_{var}_logistic_transformation" for var in mainmedia_variables if var.startswith("TV")][0]

                # # Compute coefficients for digital
                # coef_digital = np.array(grouped_media_variables_df_digital_uni["Beta"])
                # mean_digital = np.array(grouped_media_variables_df_digital_uni["transformed_mean"])
                # summation = np.sum(coef_digital * mean_digital)
                # if 'Power' in final_selected_models_df.columns:
                #     coef_digital_uni = summation / data_media[[f"scaled_{var}_power_transformation" for var in mainmedia_variables if var.startswith("Digital")][0]].mean()
                # else:
                #     coef_digital_uni = summation / data_media[[f"scaled_{var}_logistic_transformation" for var in mainmedia_variables if var.startswith("Digital")][0]].mean()

                # # Filter TV variables
                # grouped_media_variables_df_tv_uni = grouped_media_variables_df_tv[
                #     grouped_media_variables_df_tv["Variable"].isin(tv_vars)
                # ]

                # # Compute coefficients for TV
                # coef_tv = np.array(grouped_media_variables_df_tv_uni["Beta"])
                # mean_tv = np.array(grouped_media_variables_df_tv_uni["transformed_mean"])
                # summation = np.sum(coef_tv * mean_tv)
                # if 'Power' in final_selected_models_df.columns:
                #     coef_tv_uni = summation / data_media[[f"scaled_{var}_power_transformation" for var in mainmedia_variables if var.startswith("TV")][0]].mean()
                # else:
                #     coef_tv_uni = summation / data_media[[f"scaled_{var}_logistic_transformation" for var in mainmedia_variables if var.startswith("TV")][0]].mean()


                # final_coef = final_coef_df[["Variable",	"Beta"]]
                # # final_coef

                # market = "Cluster"
                # intercept = inter

                # model_results_df = final_selected_models_df.copy()
                # # model_results_df

                # # Transpose the data
                # df_transposed = final_coef.set_index("Variable").T

                # # Add Market and Intercept as new columns
                # df_transposed["Region"] = market
                # df_transposed["beta0"] = intercept

                # # df_final = df_transposed[columns_order]
                # df_final = df_transposed
                # df_final
                # 
                # Group media variables by their prefix (Digital, TV, OOH, etc.)
                # media_prefixes = set(col.split('_')[0] for col in coef_df.columns 
                #                     if any(col.startswith(x) for x in ["Digital", "TV", "OOH", "Print"]) 
                #                     and "_adjusted" in col)
                # Assume you have a consistent media order
                media_prefixes = [col.split('_')[0] for col in media_variable]  
                media_prefixes = list(set(media_prefixes))  # Unique prefixes for media vehicles

                # Create a dictionary to store grouped DataFrames
                grouped_media_dfs = {}
                for prefix in media_prefixes:
                    grouped_media_dfs[prefix] = grouped_media_variables_df[
                        grouped_media_variables_df['Variable'].str.startswith(prefix)
                    ].reset_index(drop=True)

                # Create final coefficients DataFrame
                final_coef_df = pd.concat([grouped_other_variables_df] + list(grouped_media_dfs.values()), 
                                        ignore_index=True)
                final_coef_df["Variable"] = final_coef_df["Variable"].apply(
                    lambda x: x + "_adjusted" if any(x.startswith(p) for p in media_prefixes) 
                            else "beta_scaled_" + x
                )
                # final_coef_df

                # Extract media variables dynamically from coef_df
                media_vars = {prefix: [col.replace("_adjusted", "") for col in coef_df 
                                    if col.startswith(prefix) and "Total" not in col]
                            for prefix in media_prefixes}

                # Filter and process each media type
                media_coefficients = {}
                mainmedia_variables = [col.replace('_adjusted', '') 
                                    for col in filtered_model_result.columns 
                                    if col.endswith('_adjusted') and "Total" in col]

                for prefix in media_prefixes:
                    # Filter variables for current media type
                    grouped_media_df = grouped_media_dfs[prefix][
                        grouped_media_dfs[prefix]["Variable"].isin(media_vars[prefix])].reset_index(drop=True)
                    
                    # Compute coefficients
                    coef_values = np.array(grouped_media_df["Beta"])
                    mean_values = np.array(grouped_media_df["transformed_mean"])
                    summation = np.sum(coef_values * mean_values)
                    
                    # Find the appropriate transformation column
                    transform_col = next(
                        (f"scaled_{var}_power_transformation" if 'Power' in final_selected_models_df.columns 
                        else f"scaled_{var}_logistic_transformation" 
                        for var in mainmedia_variables if var.startswith(prefix)),
                        None
                    )
                    
                    if transform_col:
                        media_coefficients[prefix] = summation / data_media[transform_col].mean()

                final_coef = final_coef_df[["Variable",	"Beta"]]
                # final_coef

                # Prepare final DataFrame
                market = "Cluster"
                intercept = inter

                df_transposed = final_coef.set_index("Variable").T
                df_transposed["Region"] = market
                df_transposed["beta0"] = intercept
                df_transposed.reset_index(drop=True, inplace=True)

                # Add computed media coefficients
                for prefix in media_prefixes:
                    if prefix in media_coefficients:
                        var_name = next((f"{var}_adjusted" for var in mainmedia_variables 
                                        if var.startswith(prefix)), None)
                        if var_name:
                            df_transposed[var_name] = media_coefficients[prefix]

                df_final = df_transposed
                # df_final

                # # Reset the index to make it a standard DataFrame
                # df_final.reset_index(drop=True, inplace=True)
                # df_final[[f"{var}_adjusted" for var in mainmedia_variables if var.startswith("TV")][0]] = coef_tv_uni
                # df_final[[f"{var}_adjusted" for var in mainmedia_variables if var.startswith("Digital")][0]] = coef_digital_uni

                model_results_df = final_selected_models_df.copy()
                # model_results_df
                
                Region_cluster_beta = pd.concat([model_results_df,df_final],ignore_index=True)

                # Identify the mask for the "Cluster" row
                mask = Region_cluster_beta["Region"] == "Cluster"

                # Fill NaN values in the "Cluster" row with values from the first row
                # Region_cluster_beta.loc[mask] = Region_cluster_beta.loc[mask].fillna(Region_cluster_beta.iloc[0])
                for col in Region_cluster_beta.columns:
                    fill_value = Region_cluster_beta.iloc[0][col]
                    if not isinstance(fill_value, list):
                        Region_cluster_beta.loc[mask, col] = Region_cluster_beta.loc[mask, col].fillna(fill_value)


                # Update session state with new results (will overwrite existing ones)
                if not Region_cluster_beta.empty:
                    st.session_state.Region_cluster_beta = Region_cluster_beta.copy()  # Always update with new results

                if 'Region_cluster_beta' in st.session_state and not st.session_state.Region_cluster_beta.empty:
                    # st.write("### Top down results with genre beta")
                    st.dataframe(st.session_state.Region_cluster_beta)
                else:
                    st.warning("No data available yet")

            # Region_cluster_beta


#################################################################### POST-MODELING ANALYSIS #####################################################################
#################################################################### POST-MODELING ANALYSIS #####################################################################
#################################################################### POST-MODELING ANALYSIS #####################################################################
#################################################################### POST-MODELING ANALYSIS #####################################################################
#################################################################### POST-MODELING ANALYSIS #####################################################################



if selected == "POST-MODEL ANALYSIS":

    import streamlit as st
    import pandas as pd
    import numpy as np
    import matplotlib.pyplot as plt
    from sklearn.preprocessing import StandardScaler, MinMaxScaler
    import plotly.graph_objects as go
    import io

    # Helper function to safely convert any value to list of floats
    def convert_to_float_list(value):
        if isinstance(value, str):
            if ',' in value:
                return list(map(float, value.split(',')))
            else:
                return [float(value)]
        elif isinstance(value, (int, float)):
            return [float(value)]
        elif isinstance(value, list):
            return list(map(float, value))
        else:
            raise ValueError(f"Unsupported value type: {type(value)}")


    # Define adstock and logistic functions
    def adstock_function(data, carryover):
        adstocked = np.zeros_like(data)
        adstocked[0] = data.iloc[0]
        for t in range(1, len(data)):
            adstocked[t] = data.iloc[t] + carryover * adstocked[t - 1]
        return adstocked

    def logistic_function(x, growth_rate, midpoint):
        return 1 / (1 + np.exp(-growth_rate * (x - midpoint)))

    # Function to calculate diminishing return predictions
    def calculate_diminishing_return_predictions(
        market, 
        media_variable, 
        dummy_media_values, 
        media_vars, 
        other_variables, 
        X_market,
        market_weights
    ):
        
        # scaler = MinMaxScaler(feature_range=(0, 1))

        # Get market-specific weights
        if market not in market_weights:
            raise ValueError(f"Market {market} not found in weights file.")
        market_data = market_weights[market]

        standardization_method = market_data["Standardization_method"]
        if standardization_method == 'minmax':
            scaler_class = MinMaxScaler
            scaler_params = {'feature_range': (0, 1)}
        elif standardization_method == 'zscore':
            scaler_class = StandardScaler
            scaler_params = {}
        elif standardization_method == 'none':
            scaler_class = None
        else:
            raise ValueError(f"Unsupported standardization method: {standardization_method}")
        

        intercept = market_data['beta0']
        adjusted_weights = {k: market_data[k] for k in market_data if k != 'beta0'}

        # Calculate constant (sum of product of beta of scaled other variables and their mean values)
        constant = 0
        for other_var in other_variables:
            if other_var in X_market.columns:
                other_var_scaled = f"beta_scaled_{other_var}"
                # latest_fy = sorted(X_market["Fiscal Year"].unique())[-1]
                # X_market = X_market[X_market["Fiscal Year"] == latest_fy]
                if scaler_class:
                    scaler = scaler_class(**scaler_params)
                    X_market[other_var_scaled] = scaler.fit_transform(X_market[other_var].values.reshape(-1, 1))
                    mean_value = np.mean(X_market[other_var_scaled])  # Mean of the scaled variable
                    beta = adjusted_weights.get(other_var_scaled, 0)  # Coefficient for the scaled variable
                    constant += beta * mean_value

       
        transformation_type = market_data["Transformation_type"]

        if transformation_type == "logistic":

            growth_rates = market_data["Growth_rate"]
            carryovers = market_data["Carryover"]
            mid_points = market_data["Mid_point"]

            # Convert values to lists of floats
            growth_rates = convert_to_float_list(growth_rates)
            carryovers = convert_to_float_list(carryovers)
            mid_points = convert_to_float_list(mid_points)
            # st.write("Growth Rates:", growth_rates)
            # st.write("Carryovers:", carryovers)
            # st.write("Mid Points:", mid_points)
            # st.write("dummy media vars:", media_variable)
            # st.write("Media variables used in model:", media_variables)

            # # Ensure all three lists are non-empty before using them
            # if growth_rates and carryovers and mid_points:
            #     if len(set(growth_rates)) == 1 and len(set(carryovers)) == 1 and len(set(mid_points)) == 1:
            #         growth_rate = [growth_rates[0]] 
            #         carryover = [carryovers[0]] 
            #         midpoint = [mid_points[0]] 
            # else:
            #     raise ValueError("One or more required columns (Growth_rate, Carryover, Mid_point) are missing or empty in region_row.")
            # scaler = scaler_class(**scaler_params)
            if not (growth_rates and carryovers and mid_points):
                raise ValueError("One or more required columns (Growth_rate, Carryover, Mid_point) are missing or empty in region_row.")

            # Get index of the dummy media variable
            if media_variable not in media_vars:
                raise ValueError(f"Dummy media variable {media_variable} not found in media_vars list.")

            dummy_index = media_vars.index(media_variable)

            # Select corresponding parameters
            growth_rate = growth_rates[dummy_index]
            carryover = carryovers[dummy_index]
            midpoint = mid_points[dummy_index]

            # st.write(growth_rate,carryover,midpoint)

            # Calculate adstocked version of original media series
            original_adstocked = adstock_function(pd.Series(X_market[media_variable]), carryover)
            mean_original = np.mean(original_adstocked)
            std_original = np.std(original_adstocked)
            original_adstocked_scaled = (original_adstocked - mean_original) / std_original
            original_logistic = logistic_function(original_adstocked_scaled, growth_rate, midpoint)
            original_logistic_min = np.min(original_logistic)
            original_logistic_max = np.max(original_logistic)

            # Calculate adstocked version of dummy series
            adstocked_dummy = adstock_function(pd.Series(dummy_media_values), carryover)

            # Scale dummy series using mean and std from original
            adstocked_values_scaled = (adstocked_dummy - mean_original) / std_original


            # adstocked = adstock_function(pd.Series(dummy_media_values), carryover)
            # adstocked_values_scaled = (adstocked - np.mean(adstocked)) / np.std(adstocked)
            # logistic_transformed_values = logistic_function(adstocked_values_scaled, growth_rate[0], midpoint[0])
            # st.write(growth_rate[0], midpoint[0], carryover[0])
            # adstocked_values_scaled = (dummy_media_values - np.mean(dummy_media_values)) / np.std(dummy_media_values)
            logistic_transformed_values = logistic_function(adstocked_values_scaled, growth_rate, midpoint)
        
        elif transformation_type == "power":

            # growth_rates = market_data["Growth_rate"]
            carryovers = market_data["Carryover"]
            powers = market_data["Power"]

            # Convert comma-separated string values into lists of floats
            # growth_rates = list(map(float, growth_rates.split(',')))
            # carryovers = list(map(float, carryovers.split(',')))
            # powers = list(map(float, powers.split(',')))
            carryovers = convert_to_float_list(carryovers)
            powers = convert_to_float_list(powers)

            # Ensure all three lists are non-empty before using them
            if carryovers and powers:
                if len(set(carryovers)) == 1 and len(set(powers)) == 1:
                    # growth_rate = [growth_rates[0]] 
                    carryover = [carryovers[0]] 
                    power = [powers[0]] 
            else:
                raise ValueError("One or more required columns (Growth_rate, Carryover, Mid_point) are missing or empty in region_row.")
            scaler = scaler_class(**scaler_params)
            # st.write(standardization_method,growth_rate,carryover,midpoint)
            
            # adstocked_values_scaled = (dummy_media_values - np.mean(dummy_media_values)) / np.std(dummy_media_values)
            adstocked_values_scaled = (dummy_media_values - np.min(dummy_media_values)) / (np.max(dummy_media_values) - np.min(dummy_media_values))
            logistic_transformed_values =  np.power(np.maximum(adstocked_values_scaled, 0), power[0])
        
            
        # Min-Max scaling for dummy media values
        # dummy_media_values_scaled = scaler.fit_transform(logistic_transformed_values.reshape(-1, 1)).flatten()

        dummy_media_values_scaled = (logistic_transformed_values - original_logistic_min) / (original_logistic_max - original_logistic_min)

        # st.write(remaining_media_var)

    # Transform all remaining media variables
        remaining_transformed_values = {}
        for remaining_media_var in media_vars:
            if remaining_media_var != media_variable:
                if transformation_type == "logistic":
                    carryover = carryovers[media_vars.index(remaining_media_var)]
                    growth_rate = growth_rates[media_vars.index(remaining_media_var)]
                    midpoint = mid_points[media_vars.index(remaining_media_var)]
                    # st.write(carryover,growth_rate,midpoint)
                    # latest_fy = sorted(X_market["Fiscal Year"].unique())[-1]
                    # X_market = X_market[X_market["Fiscal Year"] == latest_fy]
                    # Adstock and logistic transform for remaining media variable
                    adstocked_remaining = adstock_function(pd.Series(X_market[remaining_media_var]), carryover)
                    adstocked_values_scaled_re =  (adstocked_remaining - np.mean(adstocked_remaining)) / np.std(adstocked_remaining)
                    transformed_remaining = np.nan_to_num(logistic_function(adstocked_values_scaled_re, growth_rate, midpoint))
                elif transformation_type == "power":
                    carryover = carryovers[media_vars.index(remaining_media_var)]
                    # growth_rate = growth_rates[media_vars.index(remaining_media_var)]
                    power = powers[media_vars.index(remaining_media_var)]

                    # Adstock and logistic transform for remaining media variable
                    adstocked_remaining = adstock_function(pd.Series(X_market[remaining_media_var]), carryover)
                    adstocked_values_scaled_re =  (adstocked_remaining - np.mean(adstocked_remaining)) / np.std(adstocked_remaining)
                    transformed_remaining = np.power(np.maximum(adstocked_values_scaled_re,0),power)

                # Scale transformed values and store
                transformed_remaining_scaled = scaler.fit_transform(transformed_remaining.reshape(-1, 1)).flatten()
                remaining_transformed_values[remaining_media_var] = transformed_remaining_scaled
                # st.write(pd.Series(X_market[remaining_media_var]).mean())
                
        # Calculate predictions for the selected media variable
        predictions = []
        beta_x = []
        for i, transformed_dummy_value in enumerate(dummy_media_values_scaled):
            # Base prediction
            pred_y = intercept + constant + (adjusted_weights.get(f"{media_variable}_adjusted", 0)) * transformed_dummy_value
            beta_x.append(adjusted_weights.get(f"{media_variable}_adjusted", 0) * transformed_dummy_value)
            # st.write(constant)
            y = []
            # Add contributions from remaining media variables
            for remaining_media_var, transformed_values in remaining_transformed_values.items():
                # Use the transformed values of the remaining media variables for prediction
                # st.write(remaining_media_var)
                pred_y += adjusted_weights.get(f"{remaining_media_var}_adjusted", 0) * np.mean(transformed_values)
                y.append(adjusted_weights.get(f"{remaining_media_var}_adjusted", 0) * np.mean(transformed_values))
                const = intercept + constant + sum(y)
                # st.write(const)
                
                # st.write(remaining_media_var, adjusted_weights.get(f"{remaining_media_var}_adjusted", 0), np.mean(transformed_values))
                
            predictions.append(pred_y)
            # elasticity = adjusted_weights.get(f"{media_variable}_adjusted", 0) * transformed_dummy_value*(1-transformed_dummy_value)*growth_rate*(dummy_media_values/(np.std(dummy_media_values)*predictions))
            # Ensure arrays are NumPy arrays for element-wise math
            # Finalize arrays
        predictions = np.array(predictions, dtype=float)
        dummy_media_values = np.array(dummy_media_values, dtype=float)
        # sigma_beta_x = np.sum(beta_x)
        # st.write(sigma_beta_x)
        # st.write(f"Base Contribution from Non-Media Variables: {intercept+constant:.2f}")
        # st.write(const)
        # st.write(remaining_media_var, adjusted_weights.get(f"{remaining_media_var}_adjusted", 0), np.mean(transformed_values),y,const,pred_y)

        # Elasticity calculation (only for logistic transformation)
        if transformation_type == "logistic":
            beta = adjusted_weights.get(f"{media_variable}_adjusted", 0)
            elasticity = beta * logistic_transformed_values * (1 - logistic_transformed_values) * growth_rate * (dummy_media_values / (np.std(dummy_media_values) * predictions))
        else:
            elasticity = None  # Or compute an equivalent if needed for 'power'
        # Return the predictions list
        return predictions, beta_x


    # Streamlit UI to upload the dataset

    st.markdown(
        """ 
        <div style="height: 4px; background-color: black; margin: 10px 0;"></div>
        """, 
        unsafe_allow_html=True
    )
    # st.markdown(
    #     '<p style="font-size:20px; color:Black; font-weight:bold;">Upload your D1 file</p>', 
    #     unsafe_allow_html=True
    # )
    model_data = st.sidebar.file_uploader("Upload file used for Modeling", type=["csv", "xlsx"])

    # st.markdown(
    #     '<p style="font-size:20px; color:Black; font-weight:bold;">Upload Region weights file</p>', 
    #     unsafe_allow_html=True
    # )

    # File uploader to load the weights for the markets
    market_weights_file = st.sidebar.file_uploader("Final Model results", type=["csv", "xlsx"])



    # st.markdown(
    #     """ 
    #     <div style="height: 2px; background-color: black; margin: 10px 0;"></div>
    #     """, 
    #     unsafe_allow_html=True
    # )



    if model_data is not None:
        # Read data
        # df = pd.read_excel(model_data) #, sheet_name="Sheet1")
        try:
            # Load the dataset
            if model_data.name.endswith(".csv"):
                df = pd.read_csv(model_data,sheet_name="Sheet1")
            else:
                df = pd.read_excel(model_data,sheet_name="Sheet1")

        except Exception as e:
            st.error(f"Error loading file: {e}")

            # First check if df exists and is not empty
    if df is not None and not df.empty:

        # Ensure the dataset has a 'Fiscal Year' column
        if "Fiscal Year" not in df.columns:
            st.error("The uploaded dataset must contain a 'Fiscal Year' column.")
        else:
            # Step 1: Let the user select one or more Fiscal Years
            fiscal_years = df["Fiscal Year"].dropna().unique()
            selected_years = st.multiselect("Select Fiscal Year(s) for EDA", sorted(fiscal_years),default=fiscal_years)

            if selected_years:
                # Filter dataset for the selected Fiscal Years
                df = df[df["Fiscal Year"].isin(selected_years)]
                if 'Date' not in df.columns:
                    df["Date"] = pd.to_datetime(df["Year"].astype(str) + "-" + df["Month"], format="%Y-%B")

                # # Apply to your DataFrames
                # if 'df_filtered' in locals() or 'df_filtered' in globals():
                #     try:
                #         df_filtered = create_date_column(df_filtered.copy())
                #     except Exception as e:
                #         st.error(f"Error processing df_filtered: {str(e)}")

                # st.write(f"#### EDA for Fiscal Year(s) {', '.join(map(str, selected_years))}")
                with st.expander("View Filtered Dataset"):
                    st.dataframe(df, hide_index=True)

                # Show DataFrame Shape
                st.write(f"#### **Shape of Dataset:** `{df.shape[0]}` rows × `{df.shape[1]}` columns")

            st.markdown(
                """ 
                <div style="height: 2px; background-color: black; margin: 10px 0;"></div>
                """, 
                unsafe_allow_html=True
            )

    if market_weights_file:
        try:
            if market_weights_file.name.endswith(".csv"):
                market_weights_df = pd.read_csv(market_weights_file)

            else:
                # Load Excel file and list available sheets
                excel_file = pd.ExcelFile(market_weights_file)
                sheet_names = excel_file.sheet_names

                # Let user select a sheet
                selected_sheet = st.sidebar.selectbox("Select sheet", sheet_names)

                # Load the selected sheet
                market_weights_df = pd.read_excel(excel_file, sheet_name=selected_sheet)

            # st.success("File loaded successfully.")

        except Exception as e:
            st.error(f"Error loading file: {e}")



        # Convert Year column to string
        df['Year'] = df['Year'].astype(str)

        # # Create Cluster-level aggregated data
        # all_india_df = df.groupby(['Market', 'Brand', 'Year', 'Month', "Fiscal Year"], as_index=False).agg(
        #     {**{col: 'sum' for col in df.select_dtypes(include='number').columns 
        #         if col not in ['Channel', 'Variant', 'PackType', 'PPG', 'PackSize', 'Week', "D1", 'Filtered Volume Index']},
        #     'D1': 'sum',
        #     'Filtered Volume Index': 'mean'}
        # ).reset_index()
        # Create Cluster-level aggregated data
        if "KPI" in df.columns:
            # Convert Year column to string
            # df['Year'] = df['Year'].astype(str)
            all_india_df = df.groupby(['Market', 'Brand', 'Year', 'Month'], as_index=False).agg(
                {**{col: 'sum' for col in df.select_dtypes(include='number').columns if col not in ["D1","KPI"]},
                'D1': 'sum',
                "KPI": 'mean'}
            ).reset_index(drop=True)
            all_india_df["Price"] = all_india_df["Sales"]/all_india_df["Volume"]
        elif 'Filtered Volume Index' in df.columns:
            all_india_df = df.groupby(['Market', 'Brand', 'Year', 'Month', "Fiscal Year"], as_index=False).agg(
                {**{col: 'sum' for col in df.select_dtypes(include='number').columns 
                    if col not in ['Channel', 'Variant', 'PackType', 'PPG', 'PackSize', 'Week', "D1", 'Filtered Volume Index']},
                'D1': 'sum',
                'Filtered Volume Index': 'mean'}
            ).reset_index(drop=True)
        else:
            all_india_df = df.groupby(['Market', 'Brand', 'Year', 'Month', "Fiscal Year"], as_index=False).agg(
                {**{col: 'sum' for col in df.select_dtypes(include='number').columns 
                    if col not in ['Channel', 'Variant', 'PackType', 'PPG', 'PackSize', 'Week']}}
            ).reset_index(drop=True)

            # Add Price column
            all_india_df["Price"] = all_india_df["Sales"] / all_india_df["Volume"]
        all_india_df["Region"] = "Cluster"

        # User selection for Region or Cluster
        # data_option = st.radio("Select Data Source:", ["Region", "Cluster"])
        # st.markdown(
        #     '<p style="font-size:15px; color:Black; font-weight:bold;">Select Data Source:</p>', 
        #     unsafe_allow_html=True
        # )
        # data_option = st.radio("", ["Region", "Cluster"])


        # Select appropriate dataset based on user choice
        # if data_option == "Region":
        # available_regions = market_weights_df["Region"].unique().tolist()  # Get unique regions
        # st.markdown(
        #     '<p style="font-size:15px; color:black; font-weight:bold;">Select a Region:</p>', 
        #     unsafe_allow_html=True
        # )
        # selected_region = st.multiselect("", available_regions,default=available_regions)  # Empty label to avoid duplication
        # selected_df = df[df["Region"].isin(selected_region)]  # Filter data for selected region
        # selected_df = selected_df.rename(columns={"Region":"Market","Market":"Region"})
        # st.write(f"Using **Region-Level Data** for {selected_region}")
        # else:
        #     selected_df = all_india_df
        #     st.write("Using **Cluster-Level Data** for the curve.")

        # st.dataframe(selected_df)



    if market_weights_df is not None and not market_weights_df.empty:

        # # Ensure the dataset has a 'Fiscal Year' column
        # if "Brand" not in df.columns:
        #     st.error("The uploaded dataset must contain a 'Fiscal Year' column.")
        # else:
        #     # Step 1: Let the user select one or more Fiscal Years
        # brand = market_weights_df["Brand"].dropna().unique()
        # selected_brand = st.multiselect("Select Brand", sorted(brand),default=brand)

        #     # if selected_years:
        #         # Filter dataset for the selected Fiscal Years
        # market_weights_df = market_weights_df[market_weights_df["Brand"].isin(selected_brand)]
        # selected_df = selected_df[selected_df["Brand"].isin(selected_brand)]
                # market_weights_df


        # st.markdown(
        #             """ 
        #             <div style="height: 3px; background-color: black; margin: 15px 0;"></div>
        #             """, 
        #             unsafe_allow_html=True
        #             )


        st.markdown(
                        """
                        <style>
                            div.stTabs button {
                                flex-grow: 1;
                                text-align: center;
                            }
                        </style>
                        """,
                        unsafe_allow_html=True
                    )


        st.markdown("""
            <style>


            /* Make the tab text bolder */
            div.stTabs button div p {
                font-weight: 900 !important; /* Maximum boldness */
                font-size: 18px !important; /* Slightly larger text */
                color: black !important; /* Ensuring good contrast */
            }
            </style>
        """, unsafe_allow_html=True)

        tab1,tab2,tab3 = st.tabs(["Diminishing Return Curve","Contribution Charts","Waterfall Charts"])

   


        with tab1:
                
            # st.title("Diminishing Return Curve")

            if not df.empty:

                col11,col12 = st.columns(2)

                curve_df = df.copy()

                available_regions = market_weights_df["Region"].unique().tolist()  # Get unique regions
                # st.markdown(
                #     '<p style="font-size:15px; color:black; font-weight:bold;">Select a Region:</p>', 
                #     unsafe_allow_html=True
                # )
                with col11:
                    selected_region = st.multiselect("Select Regions", available_regions,default=available_regions, key="multiselect_regions")  # Empty label to avoid duplication
                selected_df = curve_df[curve_df["Region"].isin(selected_region)]  # Filter data for selected region
                brand = market_weights_df["Brand"].unique()[0]
                selected_df = selected_df[selected_df["Brand"]==brand]
                # st.markdown(
                # """ 
                # <div style="height: 2px; background-color: black; margin: 10px 0;"></div>
                # """, 
                # unsafe_allow_html=True
                # )   

                # Display selected dataframe
                # st.write(selected_df.head())
                # Extract variable names
                y_variable = market_weights_df['Y'].iloc[0]
                # y_variable
                # Example: Assuming your dataframe is called df
                market_weights_df.rename(columns={col: col.replace('beta_', '').replace('_transformed', '_adjusted') 
                   for col in market_weights_df.columns if col.endswith('_transformed') and col.startswith('beta_')}, inplace=True)

                # Assuming market_weight_df is your DataFrame
                market_weight_columns = market_weights_df.columns.tolist()
                # st.write(market_weight_columns)
                

                # Extract media genre columns (excluding aggregated ones)
                # media_genre = [
                #     col.replace("_adjusted", "") for col in market_weight_columns
                #     if any(prefix in col for prefix in ["Digital_", "TV_"]) and "Total" not in col
                # ]
                media_genre = [
                    col.replace("_adjusted", "") for col in market_weight_columns
                    if col.endswith('_adjusted') and "Total" not in col
                ]
                # st.write(media_genre)

                # media_cost_col = [col.repl for col in media_genre]


                # Extract aggregated media columns
                aggregated_media = [
                    col.replace("_adjusted", "") for col in market_weight_columns if col.endswith('_adjusted') and "Total" in col
                ]

                # Sidebar option to choose between Media Genre and Aggregated Media
                media_selection_type = st.sidebar.radio("Select Media Type:", ["Media Genre", "Aggregated Media"])

                # Set media variables automatically based on selection type
                if media_selection_type == "Media Genre":
                    media_variables = media_genre  # Automatically set to all media_genre values
                else:
                    media_variables = aggregated_media  # Automatically set to all aggregated_media values

                other_variables = [
                col.replace("beta_scaled_", "") for col in market_weight_columns
                if col.startswith("beta_scaled_") and col not in media_genre + aggregated_media ]
                # st.write(other_variables)
                fiscal_year_column = 'Fiscal Year'

                market_weights = market_weights_df.set_index('Region').to_dict(orient='index')
                # market_weights
                # st.write(market_weights_df.columns)
                # Get the market names
                markets = selected_df['Region'].unique()

                # # # Function to find the point where the curve starts to diminish in the second half
                # def find_diminishing_point(dummy_media_values, predictions, threshold=0.001):
                #     slopes = np.diff(predictions) / np.diff(dummy_media_values)

                #     # Find the point *after* the peak slope where slope starts consistently declining
                #     max_slope_idx = np.argmax(slopes)

                #     # Only look after the inflection point
                #     slopes_after = slopes[max_slope_idx:]
                #     values_after = dummy_media_values[max_slope_idx:]
                #     preds_after = predictions[max_slope_idx:]

                #     # Define a diminishing threshold — e.g., 5% of max slope or absolute value
                #     diminishing_threshold = threshold * slopes[max_slope_idx]

                #     try:
                #         diminishing_idx = np.where(slopes_after < diminishing_threshold)[0][0]
                #         return values_after[diminishing_idx], preds_after[diminishing_idx]
                #     except IndexError:
                #         # Fallback if never diminishes below threshold
                #         return values_after[-1], preds_after[-1]
                    
                # Function to find the point where the curve starts to diminish in the second half
                def find_diminishing_point(dummy_media_values, predictions):
                    slopes = np.diff(predictions) / np.diff(dummy_media_values)
                    second_half_start = len(slopes) // 2
                    second_half_slopes = slopes[second_half_start:]
                    diminishing_point_index = np.argmax(second_half_slopes < np.percentile(second_half_slopes, 70))
                    diminishing_point_value = dummy_media_values[second_half_start + diminishing_point_index]
                    diminishing_point_prediction = predictions[second_half_start + diminishing_point_index]
                    return diminishing_point_value, diminishing_point_prediction
                    
                    


                import numpy as np

                def find_start_point(dummy_media_values, predictions):
                    slopes = np.diff(predictions) / np.diff(dummy_media_values)
                    
                    # Define first half dynamically
                    first_half_start = len(slopes) // 4  # Adjust starting point
                    first_half_end = len(slopes) // 2    # Midpoint as the end of first half
                    
                    first_half_slopes = slopes[first_half_start:first_half_end]
                    
                    # Compute the threshold (70th percentile)
                    threshold = np.percentile(first_half_slopes, 30)    # 25 for digital genre cluster
                    # threshold
                    
                    # Find the first index where the slope drops below the threshold
                    valid_indices = np.where(first_half_slopes > threshold)[0]
                    # valid_indices
                    
                    if len(valid_indices) > 0:
                        diminishing_point_index = valid_indices[0]  # First valid index
                    else:
                        diminishing_point_index = 0  # Default to 0 if no valid index is found
                    # diminishing_point_index
                    
                    start_point_value = dummy_media_values[first_half_start + diminishing_point_index]
                    start_point_prediction = predictions[first_half_start + diminishing_point_index]
                    
                    return start_point_value, start_point_prediction

                ############### Generate Scaled Media Series ###############

                def generate_scaled_media_series(recent_series, x_range):
                    scaled_series_list = []
                    percent_changes = []
                    for x in x_range:
                        new_series = [v * (1 + x) for v in recent_series]
                        scaled_series_list.append(new_series)
                        percent_changes.append(x * 100)  # Store as percentage
                    return scaled_series_list, percent_changes

                
                ############### Apply Transformations and Get Predictions ###############

                def apply_transformations(market, media_variable, scaled_series_list, media_vars, other_variables, X_market, market_weights):
                    all_predictions = []
                    all_reaches = []
                    all_beta_x = []
                    
                    for scaled_series in scaled_series_list:
                        predictions, beta_x = calculate_diminishing_return_predictions(
                            market,
                            media_variable,
                            np.array(scaled_series),
                            media_vars,
                            other_variables,
                            X_market,
                            market_weights
                        )
                        all_predictions.append(predictions)
                        all_reaches.append(np.array(scaled_series))
                        all_beta_x.append(beta_x)

                    return all_reaches, all_predictions, all_beta_x

                ############### Aggregate Reach and Predictions Across Markets ###############

                def aggregate_reach_and_predictions(all_reaches, all_predictions, all_beta_x):
                    """
                    all_reaches : list of arrays of reach values
                    all_predictions : list of arrays of prediction values
                    Returns summed reach and summed predictions
                    """
                    summed_reach = np.sum(all_reaches, axis=0)
                    summed_prediction = np.sum(all_predictions, axis=0)
                    summed_beta_x = np.sum(all_beta_x, axis=0)
                    return summed_reach, summed_prediction, summed_beta_x
                
                ############### Curve IOptions ########################################

                with col12:

                    curve_option = st.multiselect(
                        "Select curves to display",
                        options=["Volume", "Marginal ROI", "ROI"],
                        default=["Volume", "Marginal ROI", "ROI"]
                    )


                import numpy as np 
                def plot_diminishing_return_curve_with_point(
                    markets, 
                    stacked_data, 
                    media_variables, 
                    other_variables
                ):
                    max_reach_data = []  # List to store max reach data for export
                    # plots = []  # Store figures to manage layout
                    # axis_controls = []  # To store user input for axis controls
                    results = []
                    
                    annotation_offsets = {'x': 10, 'y': 30}  # Default offset for annotation placement
                    for market in markets:
                        market_data = stacked_data[stacked_data['Region'] == market].copy().fillna(0)
                        st.subheader(market)

                        Y =market_data[y_variable]
                        # Y
                        own_media_variables = [var for var in media_variables if "TV" in var or "Digital" in var]    # for GCPL
                        # st.write(media_variables)
                        plots = []  # Reset plots for this market
                        axis_controls = []  # Reset axis controls if used per market

                        for media_variable in own_media_variables:
                            grouped_sums = market_data.groupby(fiscal_year_column)[media_variable].sum()

                            # Get the most recent fiscal year
                            recent_fy = market_data[fiscal_year_column].max()

                            # Filter data for this fiscal year
                            recent_data = market_data[market_data[fiscal_year_column] == recent_fy].sort_values("Date")

                            # Extract the series of media variable values
                            recent_series = recent_data[media_variable].values
                            # st.write(grouped_sums)
                            # # st.write(market_data.columns)
                            # price_grouped_sums = market_data.groupby(fiscal_year_column)['Price'].mean()
                            # # avg_price = price_grouped_sums.mean()
                            # price_grouped_sums = price_grouped_sums.sort_index()
                            # recent_year_avg_price = price_grouped_sums.iloc[-1]
                            # Group by fiscal year and calculate average price from last 3 months
                            def last_3_month_avg_price(group):
                                group = group.sort_values("Date")
                                return group['Price'].tail(3).mean()

                            price_grouped_sums = market_data.groupby(fiscal_year_column).apply(last_3_month_avg_price)

                            # Make sure index is ordered if you want to get most recent year
                            price_grouped_sums = price_grouped_sums.sort_index()

                            # Get last fiscal year's 3-month average price
                            recent_year_avg_price = price_grouped_sums.iloc[-1]

                            # price_grouped_sums = price_grouped_sums["Price"].mean()
                            # media_variable
                            # Replace the last part after the last underscore with 'Cost'
                            cost_var = '_'.join(media_variable.split('_')[:1] + ['Spends'])
                            # cost_var
                            # media_variable
                            
                            if media_variable in df.columns and cost_var in df.columns:
                                total_media = df[media_variable].sum()
                                total_cost = df[cost_var].sum()

                                # Avoid division by zero
                                cost_per_unit = total_cost / (total_media) if total_media != 0 else None
                                # cost_per_unit
                            # FY23_total = grouped_sums.get('FY23', 0)
                            # # FY23_total
                            # FY24_total = grouped_sums.get('FY24', 0)
                            # ---- Get user-selected fiscal years from UI ----
                            selected_fiscal_years = market_data[fiscal_year_column].unique()#st.multiselect("Select Fiscal Years", options=grouped_sums.index.tolist(), default=["FY23", "FY24"])

                            # ---- Collect total values for selected years ----
                            fy_totals = {fy: grouped_sums.get(fy, 0) for fy in selected_fiscal_years}
                            # fy_totals

                            max_media_value = grouped_sums.mean()
                            if max_media_value == 0:
                                continue

                            # st.write("Max Media Value:", max_media_value)
                            # st.write("Grouped Sums:", grouped_sums)
                            # ---- Setup dummy media values for curve ----
                            max_reach = max(sum(fy_totals.values()) / len(fy_totals) if fy_totals else 0, 1)#max(list(fy_totals.values()) + [1])  # avoid 0
                            # st.write(f"Max Reach for {media_variable} in {market}: {max_reach}")
                            num_points = 200
                            # EXPAND RANGE AROUND ACTUAL VALUES — SLIGHTLY WIDER TO CATCH FULL LOGISTIC CURVE
                            padding_factor = 2  # or 2.0 if needed
                            step = max_reach * 2 / (num_points - 1)
                            start = max(min(fy_totals.values()) - (num_points // 2) * step, 0)
                            end = max(fy_totals.values()) + (num_points // 2 - 1) * step#* padding_factor
                            dummy_media_values = np.arange(start, end + step, step)
                            # avg_reach = np.mean(list(fy_totals.values())) if fy_totals else 1
                            # min_reach = min(fy_totals.values()) if fy_totals else 0
                            # max_reach = max(fy_totals.values()) if fy_totals else 2

                            # # Calculate range that covers all data but is centered around average
                            # range_size = max(avg_reach - min_reach, max_reach - avg_reach) * 1.5  # 1.5x buffer
                            # start = max(avg_reach - range_size, 0)
                            # end = avg_reach + range_size
                            # num_points = 100
                            # dummy_media_values = np.linspace(start, end, num_points)
                            # ---- Setup dummy media values for curve ----
                            # Calculate average reach instead of max
                            # avg_reach = np.mean(list(fy_totals.values())) if fy_totals else 1  # fallback to 1 if empty
                            # num_points = 100
                            # step = avg_reach * 2 / (num_points - 1)  # Scale step based on average

                            # # Calculate start and end points centered around the average
                            # start = max(avg_reach - (num_points // 2) * step, 0)  # Ensure start is not negative
                            # end = avg_reach + (num_points // 2 - 1) * step

                            # dummy_media_values = np.arange(start, end + step, step)

                            # # Calculate predictions
                            # predictions, beta_x = calculate_diminishing_return_predictions(
                            #     market, 
                            #     media_variable, 
                            #     dummy_media_values, 
                            #     media_variables, 
                            #     other_variables, 
                            #     market_data,
                            #     market_weights
                            # )
                            # st.write(predictions)

                            # x_range = np.linspace(-0.5, 0.5, 51)  # Example range for +/-50% variation
                            # Sidebar inputs for x_range parameters
                            with st.sidebar.expander(f"{media_variable} Settings"):
                                start_pct = st.number_input("Start %", min_value=-100.0, max_value=0.0, value=-50.0, step=1.0, key=f"start_pct_{media_variable}_{market}")
                                end_pct = st.number_input("End %", min_value=0.0, max_value=200.0, value=50.0, step=1.0, key=f"end_pct_{media_variable}_{market}")
                                num_points = st.number_input("Number of points", min_value=2, max_value=1000, value=51, step=1, key=f"num_points_{media_variable}_{market}")

                            # Convert percent to fraction
                            start = start_pct / 100
                            end = end_pct / 100

                            # Create x_range based on user input
                            x_range = np.linspace(start, end, int(num_points))

                            # Step 1 — Get recent fiscal year's media series
                            # recent_series = list(grouped_sums.iloc[-1:])  # Or however you extract it

                            # Step 2 — Generate scaled series
                            scaled_series_list, percent_changes = generate_scaled_media_series(recent_series, x_range)

                            # Step 3 — Apply transformations
                            all_reaches, all_predictions, all_beta_x = apply_transformations(
                                market,
                                media_variable,
                                scaled_series_list,
                                media_variables,
                                other_variables,
                                market_data,
                                market_weights
                            )

                            # Step 4 — Aggregate
                            summed_reach, summed_prediction, summed_beta_x = aggregate_reach_and_predictions(all_reaches, all_predictions, all_beta_x)
                            # st.write(summed_reach, summed_prediction)
                            # Step 4 — Aggregate per series
                            # For each series, calculate the sum (or mean) of reach and prediction
                            summed_reach = np.array([np.sum(reach_series) for reach_series in all_reaches])
                            summed_prediction = np.array([np.sum(pred_series) for pred_series in all_predictions])
                            summed_beta_x = np.array([np.sum(beta_series) for beta_series in all_beta_x])

                            # Now all lists have the same length as percent_changes
                            # st.dataframe(pd.DataFrame({
                            #     "Percent Change (%)": percent_changes,
                            #     "Reach": summed_reach,
                            #     "Prediction": summed_prediction
                            # }))

                            # Now you can use summed_reach and summed_prediction as needed


                            if media_variable in df.columns and cost_var in df.columns:

                                # Assume cost per GRP is known (e.g., 5000)
                                media_spend = summed_reach * cost_per_unit 
                                # media_spend  

                                # Calculate ROI as incremental volume / spend
                                media_marginal_roi = np.gradient(summed_prediction)*recent_year_avg_price / np.gradient(media_spend)  # approximate marginal ROI
                                media_roi = summed_beta_x*recent_year_avg_price / media_spend
                                # st.write(media_roi)

                
                            # Find the diminishing point
                            diminishing_point_value, diminishing_point_prediction = find_diminishing_point(summed_reach, summed_prediction)

                            # Find the start point
                            start_point_value, start_point_prediction = find_start_point(summed_reach, summed_prediction)

                            
                            # Store data for export
                            for dummy_value, prediction in zip(summed_reach, summed_prediction):
                                results.append({
                                    "Brand": brand,
                                    "Market": market,
                                    "Media Variable": media_variable,
                                    "Reach": dummy_value,
                                    "Prediction": prediction,
                                    # "Constant": const,
                                    # "Remaining media Variables": remaining_media_var,
                                    # "Remaining Media Var const": y
                                })

                        
                            # ---- Prepare output dictionary ----
                            fy_prediction_data = {}
                            for fy, total in fy_totals.items():
                                prediction = summed_prediction[(np.abs(summed_reach - total)).argmin()]
                                fy_prediction_data[fy] = {
                                    "total": total,
                                    "prediction": prediction
                                    }
                                
                            # ---- Prepare output dictionary ----
                            fy_roi_data = {}
                            for fy, total in fy_totals.items():
                                roi = media_roi[(np.abs(summed_reach - total)).argmin()]
                                fy_roi_data[fy] = {
                                    "total": total,
                                    "roi": roi
                                    }
                                
                            # ---- Prepare output dictionary ----
                            fy_marginal_roi_data = {}
                            for fy, total in fy_totals.items():
                                marginal_roi = media_marginal_roi[(np.abs(summed_reach - total)).argmin()]
                    
                                fy_marginal_roi_data[fy] = {
                                    "total": total,
                                    "marginal_roi": marginal_roi
                                    }
                                
                            # Find the closest index for start and end
                            start_idx = (np.abs(summed_reach - start_point_value)).argmin()
                            end_idx = (np.abs(summed_reach - diminishing_point_value)).argmin()

                            # Create the dictionary for ROI
                            points_roi_data = {
                                "start": {
                                    "total": start_point_value,
                                    "roi": media_roi[start_idx]
                                },
                                "end": {
                                    "total": diminishing_point_value,
                                    "roi": media_roi[end_idx]
                                }
                            }

                            # Create the dictionary for Marginal ROI
                            points_marginal_roi_data = {
                                "start": {
                                    "total": start_point_value,
                                    "marginal_roi": media_marginal_roi[start_idx]
                                },
                                "end": {
                                    "total": diminishing_point_value,
                                    "marginal_roi": media_marginal_roi[end_idx]
                                }
                            }
                                
                            # st.dataframe(fy_roi_data)
                                
                            # ---- Store results ----
                            result_row = {
                                "Market": market,
                                "Media Variable": media_variable,
                                "Max Reach": diminishing_point_value,
                                "Min Reach": start_point_value,
                                "Diminishing Point Prediction": diminishing_point_prediction,
                                "Diminishing Point Marginal ROI": points_marginal_roi_data["end"]["marginal_roi"],
                                "Diminishing Point ROI": points_roi_data["end"]["roi"],
                                # "Start Point marginal ROI": points_marginal_roi_data["start"]["marginal_roi"],
                                # "Start Point ROI": points_roi_data["start"]["roi"],
                                # "Start Point Marginal ROI": start_point_marginal_roi,
                                # "Start Point ROI": start_point_roi
                            }
                            # Add FY values to result_row
                            for fy, data in fy_prediction_data.items():
                                result_row[f"{fy}"] = data["total"]
                                result_row[f"{fy} Prediction"] = data["prediction"]
                            # max_reach_data.append(result_row)

                            # Add FY values to result_row
                            for fy, data in fy_roi_data.items():
                                result_row[f"{fy}"] = data["total"]
                                result_row[f"{fy} ROI"] = data["roi"]
                            # max_reach_data.append(result_row)

                            # Add FY values to result_row
                            for fy, data in fy_marginal_roi_data.items():
                                result_row[f"{fy}"] = data["total"]
                                result_row[f"{fy} Marginal ROI"] = data["marginal_roi"]
                            max_reach_data.append(result_row)

                            # Create the plot
                            fig = go.Figure()

                            if "Volume" in curve_option:

                                # Add diminishing return curve
                                fig.add_trace(go.Scatter(
                                    x=summed_reach, 
                                    y=summed_prediction, 
                                    mode='lines',
                                    line=dict(color='navy'),
                                    showlegend=False,  # Disable legend
                                    yaxis='y1'  # This is the default, but being explicit
                                ))


                            if media_variable in df.columns and cost_var in df.columns:

                                if "Marginal ROI" in curve_option:

                                    fig.add_trace(go.Scatter(
                                        x=summed_reach,
                                        y=media_marginal_roi,
                                        mode='lines',
                                        line=dict(color='green'),
                                        name='Marginal ROI',
                                        yaxis='y2'
                                    ))

                                if "ROI" in curve_option:

                                    fig.add_trace(go.Scatter(
                                        x=summed_reach,
                                        y=media_roi,
                                        mode='lines',
                                        line=dict(color='purple'),
                                        name='ROI',
                                        yaxis='y2'
                                    ))

                            # Determine if all options are selected
                            if set(curve_option) == {"Volume", "ROI", "Marginal ROI"}:
                                show_volume_annotations_only = True
                            else:
                                show_volume_annotations_only = False

                            import plotly.colors as pc

                            # Create a color palette (you can customize or extend this)
                            fy_colors = pc.qualitative.Set2  # or Set2, Pastel1, etc.

                            if "Volume" in curve_option:

                                if not show_volume_annotations_only or show_volume_annotations_only:

                                    # Add vertical lines for each fiscal year with different colors
                                    for i, (fy, data) in enumerate(fy_prediction_data.items()):
                                        color = fy_colors[i % len(fy_colors)]  # Cycle through colors if there are more FYs than colors

                                        fig.add_trace(go.Scatter(
                                            x=[data["total"], data["total"]],
                                            y=[0, data["prediction"]],
                                            mode='lines',
                                            name=f"{fy} Reach",
                                            line=dict(color=color),  # Solid line with unique color
                                            showlegend=False
                                        ))

                            if "ROI" in curve_option and not show_volume_annotations_only:

                                # Add vertical lines for each fiscal year with different colors
                                for i, (fy, data) in enumerate(fy_roi_data.items()):
                                    color = fy_colors[i % len(fy_colors)]  # Cycle through colors if there are more FYs than colors

                                    fig.add_trace(go.Scatter(
                                        x=[data["total"], data["total"]],
                                        y=[0, data["roi"]],
                                        mode='lines',
                                        name=f"{fy} Reach",
                                        line=dict(color=color),  # Solid line with unique color
                                        yaxis='y2',
                                        showlegend=False
                                    ))

                            if "Marginal ROI" in curve_option and not show_volume_annotations_only:

                                # Add vertical lines for each fiscal year with different colors
                                for i, (fy, data) in enumerate(fy_marginal_roi_data.items()):
                                    color = fy_colors[i % len(fy_colors)]  # Cycle through colors if there are more FYs than colors

                                    fig.add_trace(go.Scatter(
                                        x=[data["total"], data["total"]],
                                        y=[0, data["marginal_roi"]],
                                        mode='lines',
                                        name=f"{fy} Reach",
                                        line=dict(color=color),  # Solid line with unique color
                                        yaxis='y2',
                                        showlegend=False
                                    ))



                            if "Volume" in curve_option:

                                if not show_volume_annotations_only or show_volume_annotations_only:

                                    fig.add_trace(go.Scatter(
                                        x=[diminishing_point_value, diminishing_point_value], 
                                        y=[0, diminishing_point_prediction], 
                                        mode='lines', 
                                        line=dict(color='blue'),
                                        showlegend=False
                                    ))

                                    fig.add_trace(go.Scatter(
                                        x=[start_point_value, start_point_value],
                                        y=[0, start_point_prediction],
                                        mode='lines',
                                        line=dict(color='orange'),
                                        showlegend=False
                                    ))

                            # Define colors for start and end points
                            point_colors = {
                                "start": "orange",
                                "end": "blue"
                            }

                            if "ROI" in curve_option and not show_volume_annotations_only:
                                # Add vertical lines for start and end points with specified colors
                                for point_name, data in points_roi_data.items():
                                    color = point_colors.get(point_name, "gray")  # Default to gray if key not found

                                    fig.add_trace(go.Scatter(
                                        x=[data["total"], data["total"]],
                                        y=[0, data["roi"]],
                                        mode='lines',
                                        name=f"{point_name.capitalize()} Point",
                                        line=dict(color=color),  # Use specified color
                                        yaxis='y2',
                                        showlegend=False
                                    ))

                            if "Marginal ROI" in curve_option and not show_volume_annotations_only:
                                # Add vertical lines for start and end points with specified colors
                                for point_name, data in points_marginal_roi_data.items():
                                    color = point_colors.get(point_name, "gray")  # Default to gray if key not found

                                    fig.add_trace(go.Scatter(
                                        x=[data["total"], data["total"]],
                                        y=[0, data["marginal_roi"]],
                                        mode='lines',
                                        name=f"{point_name.capitalize()} Point",
                                        line=dict(color=color),  # Use specified color
                                        yaxis='y2',
                                        showlegend=False
                                    ))


                            
                            # Annotations for each vertical line
                            annotations = []

                            # Function to add annotations dynamically with offsets
                            def add_annotation(x, y, text, color, xanchor, yanchor, ax=0, ay=0, **kwargs):
                                annotations.append(
                                    dict(
                                        x=x,
                                        y=y,
                                        text=text,
                                        showarrow=True,
                                        font=dict(color="black", size=17),  # Increased text size
                                        align="center",
                                        xanchor=xanchor,  # Adjust horizontal alignment
                                        yanchor=yanchor,  # Adjust vertical alignment
                                        arrowhead=2,
                                        ax=ax,
                                        ay=ay,
                                        bgcolor="white",  # Optional background color for visibility
                                        **kwargs  # This allows passing extra properties like yref
                                    )
                                )

        



                            if "Volume" in curve_option and (not show_volume_annotations_only or show_volume_annotations_only):
                            

                                # Sort years by x-value (total reach)
                                sorted_fy = sorted(fy_prediction_data.items(), key=lambda x: x[1]["total"])

                                # Identify max x (farthest fiscal year)
                                max_fy, max_data = sorted_fy[-1]

                                for fy, data in sorted_fy:
                                    x = data["total"]
                                    y = data["prediction"]
                                    formatted_value = f"{x / 1e6:.1f}M" if x >= 1e6 else f"{x / 1e3:.0f}K"
                                    label = f"{fy}, {formatted_value}"

                                    if x == 0:
                                        # Special case: put inside graph
                                        add_annotation(
                                            x=x,
                                            y=y,
                                            text=label,
                                            color="black",
                                            xanchor="left",
                                            yanchor="top",
                                            ax=10,
                                            ay=30
                                        )
                                    elif fy == max_fy:
                                        # Max reach: place above curve
                                        add_annotation(
                                            x=x,
                                            y=y,
                                            text=label,
                                            color="black",
                                            xanchor="center",
                                            yanchor="top",
                                            ax=0,
                                            ay=-60
                                        )
                                    else:
                                        # Other years: place to the side
                                        add_annotation(
                                            x=x,
                                            y=y,
                                            text=label,
                                            color="black",
                                            xanchor="right",
                                            yanchor="top",
                                            ax=-10,
                                            ay=annotation_offsets.get('y', -40)  # fallback if annotation_offsets not defined
                                        )

                            if "ROI" in curve_option and not show_volume_annotations_only:

                                # Sort years by x-value (total reach)
                                sorted_fy = sorted(fy_roi_data.items(), key=lambda x: x[1]["total"])

                                # Identify max x (farthest fiscal year)
                                max_fy, max_data = sorted_fy[-1]

                                for fy, data in sorted_fy:
                                    x = data["total"]
                                    y = data["roi"]
                                    formatted_value_y = f"{y :.1f}" 
                                    formatted_value_x = f"{x / 1e6:.1f}M" if x >= 1e6 else f"{x / 1e3:.0f}K"
                                    label = f"{fy}: {formatted_value_x}, {formatted_value_y}"

                                    if x == 0:
                                        # Special case: put inside graph
                                        add_annotation(
                                            x=x,
                                            y=y,
                                            text=label,
                                            color="black",
                                            xanchor="left",
                                            yanchor="top",
                                            ax=10,
                                            ay=30,
                                            yref="y2"
                                        )
                                    elif fy == max_fy:
                                        # Max reach: place above curve
                                        add_annotation(
                                            x=x,
                                            y=y,
                                            text=label,
                                            color="black",
                                            xanchor="center",
                                            yanchor="top",
                                            ax=0,
                                            ay=-60,
                                            yref="y2"
                                        )
                                    else:
                                        # Other years: place to the side
                                        add_annotation(
                                            x=x,
                                            y=y,
                                            text=label,
                                            color="black",
                                            xanchor="right",
                                            yanchor="top",
                                            ax=-10,
                                            yref="y2",
                                            ay=annotation_offsets.get('y', -40)  # fallback if annotation_offsets not defined
                                        )

                            if "Marginal ROI" in curve_option and not show_volume_annotations_only:

                                # Sort years by x-value (total reach)
                                sorted_fy = sorted(fy_marginal_roi_data.items(), key=lambda x: x[1]["total"])

                                # Identify max x (farthest fiscal year)
                                max_fy, max_data = sorted_fy[-1]

                                for fy, data in sorted_fy:
                                    x = data["total"]
                                    y = data["marginal_roi"]
                                    formatted_value_y = f"{y :.1f}" 
                                    formatted_value_x = f"{x / 1e6:.1f}M" if x >= 1e6 else f"{x / 1e3:.0f}K"
                                    label = f"{fy}: {formatted_value_x}, {formatted_value_y}"

                                    if x == 0:
                                        # Special case: put inside graph
                                        add_annotation(
                                            x=x,
                                            y=y,
                                            text=label,
                                            color="black",
                                            xanchor="left",
                                            yanchor="top",
                                            ax=10,
                                            ay=30,
                                            yref="y2"
                                        )
                                    elif fy == max_fy:
                                        # Max reach: place above curve
                                        add_annotation(
                                            x=x,
                                            y=y,
                                            text=label,
                                            color="black",
                                            xanchor="center",
                                            yanchor="top",
                                            ax=0,
                                            ay=-60,
                                            yref="y2"
                                        )
                                    else:
                                        # Other years: place to the side
                                        add_annotation(
                                            x=x,
                                            y=y,
                                            text=label,
                                            color="black",
                                            xanchor="right",
                                            yanchor="top",
                                            ax=-10,
                                            yref="y2",
                                            ay=annotation_offsets.get('y', -40)  # fallback if annotation_offsets not defined
                                        )



                            if "Volume" in curve_option and (not show_volume_annotations_only or show_volume_annotations_only):


                                add_annotation(
                                    x=diminishing_point_value,
                                    y=diminishing_point_prediction,
                                    text=f"Max Reach, {diminishing_point_value / 1e6:.1f}M" if diminishing_point_value >= 1e6 else f"Max Reach, {diminishing_point_value / 1e3:.0f}K", #, {diminishing_point_value / 1e6:.1f}M",
                                    color="black",
                                    xanchor="left",  # Align text to the left of the arrow
                                    yanchor="top",
                                    ax=annotation_offsets['x'],
                                    ay=annotation_offsets['y']
                                )
                                add_annotation(
                                    x=start_point_value,
                                    y=start_point_prediction,
                                    text=f"Min Point, {start_point_value / 1e6:.1f}M" if start_point_value >= 1e6 else f"Min Point, {start_point_value / 1e3:.0f}K",
                                
                                    color="black",
                                    # font=dict(color="black"),
                                    xanchor="right",    # shifts label to the left of the x value
                                    yanchor="bottom",   # shifts label above the y value
                                    ax=-30,             # move left
                                    ay=-20               # move up
                                )

                            # st.write(points_roi_data)

                            
                            # Annotations for ROI
                            if "ROI" in curve_option and not show_volume_annotations_only:
                                # Start point annotation
                                add_annotation(
                                    x=points_roi_data["start"]["total"],
                                    y=points_roi_data["start"]["roi"],
                                    # text=f"{points_roi_data['start']['total'] / 1e6:.1f}M, {points_roi_data["start"]["roi"]:.1f}" if points_roi_data['start']['total'] >= 1e6 else f"{points_roi_data['start']['total'] / 1e3:.0f}K, {points_roi_data["start"]["roi"]:.1f}",
                                    color="green",
                                    xanchor="right",
                                    yanchor="bottom",
                                    ax=-30,
                                    ay=-20
                                )
                                # End point annotation
                                add_annotation(
                                    x=points_roi_data["end"]["total"],
                                    y=points_roi_data["end"]["roi"],
                                    # text=f"{points_roi_data['end']['total'] / 1e6:.1f}M, {points_roi_data["end"]["roi"]:.1f}" if points_roi_data['end']['total'] >= 1e6 else f"Max Reach, {points_roi_data['end']['total'] / 1e3:.0f}K, {points_roi_data["end"]["roi"]:.1f}", #, {diminishing_point_value / 1e6:.1f}M",
                                    color="blue",
                                    xanchor="left",
                                    yanchor="top",
                                    ax=30,
                                    ay=20
                                )

                                # st.write(points_roi_data["start"]["roi"])

            

                            # Annotations for Marginal ROI
                            if "Marginal ROI" in curve_option and not show_volume_annotations_only:
                                # Start point annotation
                                add_annotation(
                                    x=points_marginal_roi_data["start"]["total"],
                                    y=points_marginal_roi_data["start"]["marginal_roi"],
                                    # text=f"MR, {points_marginal_roi_data["start"]["marginal_roi"]:.1f}",
                                    # text=f"{points_marginal_roi_data['start']['total'] / 1e6:.1f}M, {points_marginal_roi_data["start"]["marginal_roi"]:.1f}" if points_marginal_roi_data['start']['total'] >= 1e6 else f"{points_marginal_roi_data['start']['total'] / 1e3:.0f}K, {points_marginal_roi_data["start"]["marginal_roi"]:.1f}",
                                    color="orange",
                                    xanchor="right",
                                    yanchor="bottom",
                                    ax=-30,
                                    ay=-20
                                )
                                # End point annotation
                                add_annotation(
                                    x=points_marginal_roi_data["end"]["total"],
                                    y=points_marginal_roi_data["end"]["marginal_roi"],
                                    # text=f"MR, {points_marginal_roi_data["end"]["marginal_roi"]:.1f}", #, {diminishing_point_value / 1e6:.1f}M",
                                    # text=f"{points_marginal_roi_data['end']['total'] / 1e6:.1f}M, {points_marginal_roi_data["end"]["marginal_roi"]:.1f}" if points_marginal_roi_data['end']['total'] >= 1e6 else f"Max Reach, {points_marginal_roi_data['end']['total'] / 1e3:.0f}K, {points_marginal_roi_data["end"]["marginal_roi"]:.1f}", #, {diminishing_point_value / 1e6:.1f}M",
                                    color="blue",
                                    xanchor="left",
                                    yanchor="bottom",
                                    ax=30,
                                    ay=-20
                                )


                    
                           
                            
                            if media_variable in df.columns and cost_var in df.columns:
                                # Combine all Y values: curve and fiscal year predictions
                                # all_y_values = list(predictions) #+ [data["prediction"] for data in fy_prediction_data.values()]
                                # all_y_values
                                # Find min and max of Y values
                                # Y
                                y_min = min(summed_prediction)
                                # y_min
                                y_max = max(summed_prediction)
                                # y_max
                                y_mean = summed_prediction.mean()

                                # Add padding (e.g., 5% buffer)
                                y_range_padding = 0.0001 * (y_mean)
                                # y_range_padding
                                y_min = y_min - y_range_padding
                                # y_min
                                y_max = y_max + y_range_padding
                                # Find min and max of Y values
                                y2_min = min(media_marginal_roi)
                                # y_min
                                y2_max = max(media_marginal_roi)
                                # y_max
                                y2_mean = media_marginal_roi.mean()

                                # Add padding (e.g., 5% buffer)
                                y_range_padding = 0.5 * (y2_mean)
                                # y_range_padding
                                # y2_min = y2_min + y_range_padding
                                # # y_min
                                # y2_max = y2_max - y_range_padding

                                # Set axis controls
                                axis_controls.append({
                                    'x_min': min(summed_reach),
                                    'x_max': max(summed_reach),
                                    'y_min': y_min,
                                    'y_max': y_max,
                                    'y2_min': y2_min,
                                    'y2_max': y2_max
                                })

                                # Add annotations to the plot
                                fig.update_layout(annotations=annotations)

                                # **Move sidebar controls inside the loop**
                                st.sidebar.write(f"**Adjust Axis Range for {market} - {media_variable}**")
                                x_min = st.sidebar.number_input(
                                    "Set X-axis Min", value=min(summed_reach), key=f"x_min_{market}_{media_variable}"
                                )
                                x_max = st.sidebar.number_input(
                                    "Set X-axis Max", value=max(summed_reach), key=f"x_max_{market}_{media_variable}"
                                )
                                y_min = st.sidebar.number_input(
                                    "Set Y-axis Min", value=y_min, key=f"y_min_{market}_{media_variable}"
                                )
                                y_max = st.sidebar.number_input(
                                    "Set Y-axis Max", value=y_max, key=f"y_max_{market}_{media_variable}"
                                )
                                y2_min = st.sidebar.number_input(
                                    "Set Y-axis Min", value=y2_min, key=f"y2_min_{market}_{media_variable}"
                                )
                                y2_max = st.sidebar.number_input(
                                    "Set Y-axis Max", value=y2_max, key=f"y2_max_{market}_{media_variable}"
                                )

                                # st.write(market)

                                # Update layout with user-defined axis ranges
                                fig.update_layout(
                                    # title=f"Market Response: {media_variable}",  # {market} - 
                                    title={
                                        # "text": f"Market Response Curve: {" ".join(media_variable.split("_")[:3])} ({market})",
                                        "text": f"{media_variable}",
                                        "x": 0.5,  # Centers the title
                                        "xanchor": "center",  # Ensures proper alignment
                                        "yanchor": "top"  # Keeps the title at the top
                                    },
                                    # xaxis_title="Reach",
                                    yaxis_title="Volume",
                                    xaxis=dict(
                                        range=[x_min, x_max],  # User-defined range
                                        showgrid=False,
                                        title_font=dict(color="black"),  # X-axis title in black
                                        tickfont=dict(color="black"),  # X-axis tick labels in black
                                        color="black"  # Ensure all x-axis elements are black
                                    ),
                                    yaxis=dict(
                                        range=[y_min, y_max],  # User-defined range
                                        showgrid=False,
                                        title_font=dict(color="black"),
                                        tickfont=dict(color="black")
                                    ),
                                    yaxis2=dict(
                                        title="ROI",
                                        overlaying='y',
                                        side='right',
                                        showgrid=False,
                                        title_font=dict(color="green"),
                                        tickfont=dict(color="black"),
                                        range=[y2_min, y2_max]
                                        # Adjust range based on your ROI data
                                        # range=[min(tv_roi)*0.9, max(tv_roi)*1.1] if tv_roi else [0, 100]
                                    ),
                                    template="plotly_white"
                                )
                            else:
                                # Combine all Y values: curve and fiscal year predictions
                                # all_y_values = list(predictions) #+ [data["prediction"] for data in fy_prediction_data.values()]
                                # all_y_values
                                # Find min and max of Y values
                                y_min = min(Y)
                                # y_min
                                y_max = max(Y)
                                # y_max
                                y_mean = Y.mean()

                                # Add padding (e.g., 5% buffer)
                                y_range_padding = 2 * (y_mean)
                                # y_range_padding
                                y_min = y_min + y_range_padding
                                # y_min
                                y_max = y_max - y_range_padding
                                # Find min and max of Y values
                                y2_min = min(media_marginal_roi)
                                # y_min
                                y2_max = max(media_marginal_roi)
                                # y_max
                                y2_mean = media_marginal_roi.mean()

                                # Add padding (e.g., 5% buffer)
                                y_range_padding = 0.5 * (y2_mean)
                                # y_range_padding
                                y2_min = y2_min + y_range_padding
                                # y_min
                                y2_max = y2_max - y_range_padding

                                # Set axis controls
                                axis_controls.append({
                                    'x_min': min(summed_reach),
                                    'x_max': max(summed_reach),
                                    'y_min': y_min,
                                    'y_max': y_max,
                                    'y2_min': y2_min,
                                    'y2_max': y2_max
                                })

                                # fig.update_layout(
                                #     margin=dict(b=80)  # Increase bottom margin to ensure space for annotations
                                # )
                                max_value = max(media_marginal_roi) * 1.1  # Slightly higher to give space above the data

                                fig.update_yaxes(range=[0, max_value], secondary_y=True)


                                # Add annotations to the plot
                                fig.update_layout(annotations=annotations)

                                # **Move sidebar controls inside the loop**
                                st.sidebar.write(f"**Adjust Axis Range for {market} - {media_variable}**")
                                x_min = st.sidebar.number_input(
                                    "Set X-axis Min", value=min(dummy_media_values), key=f"x_min_{market}_{media_variable}"
                                )
                                x_max = st.sidebar.number_input(
                                    "Set X-axis Max", value=max(dummy_media_values), key=f"x_max_{market}_{media_variable}"
                                )
                                y_min = st.sidebar.number_input(
                                    "Set Y-axis Min", value=y_min, key=f"y_min_{market}_{media_variable}"
                                )
                                y_max = st.sidebar.number_input(
                                    "Set Y-axis Max", value=y_max, key=f"y_max_{market}_{media_variable}"
                                )
                                y2_min = st.sidebar.number_input(
                                    "Set Y-axis Min", value=y2_min, key=f"y2_min_{market}_{media_variable}"
                                )
                                y2_max = st.sidebar.number_input(
                                    "Set Y-axis Max", value=y2_max, key=f"y2_max_{market}_{media_variable}"
                                )



                                # Update layout with user-defined axis ranges
                                fig.update_layout(
                                    # title=f"Market Response: {media_variable}",  # {market} - 
                                    title={
                                        # "text": f"Market Response Curve: {" ".join(media_variable.split("_")[:3])} ({market})",
                                        "text": f"{media_variable}",
                                        "x": 0.6,  # Centers the title
                                        "xanchor": "center",  # Ensures proper alignment
                                        "yanchor": "top"  # Keeps the title at the top
                                    },
                                    # xaxis_title="Reach",
                                    yaxis_title="Volume",
                                    xaxis=dict(
                                        range=[x_min, x_max],  # User-defined range
                                        showgrid=False,
                                        title_font=dict(color="black"),  # X-axis title in black
                                        tickfont=dict(color="black"),  # X-axis tick labels in black
                                        color="black"  # Ensure all x-axis elements are black
                                    ),
                                    yaxis=dict(
                                        range=[y_min, y_max],  # User-defined range
                                        showgrid=False,
                                        title_font=dict(color="black"),
                                        tickfont=dict(color="black")
                                    ),
                                    yaxis2=dict(
                                        title="ROI",
                                        overlaying='y',
                                        side='right',
                                        showgrid=False,
                                        title_font=dict(color="green"),
                                        tickfont=dict(color="black"),
                                        range=[y2_min, y2_max]
                                        # Adjust range based on your ROI data
                                        # range=[min(tv_roi)*0.9, max(tv_roi)*1.1] if tv_roi else [0, 100]
                                    ),
                                    template="plotly_white"
                                )
                            

                            # Show the plot in Streamlit
                            # st.plotly_chart(fig)
                            # Store figure
                            plots.append(fig)
                            axis_controls.append({
                                'x_min': min(summed_reach),
                                'x_max': max(summed_reach),
                                'y_min': 95,
                                'y_max': 112
                            })
                            

                        # **Dynamically arrange plots in rows of up to 3**
                        num_plots = len(plots)
                        num_rows = (num_plots // 2) + (1 if num_plots % 2 != 0 else 0)  # Ensure extra row if needed

                        for i in range(num_rows):
                            cols = st.columns(2)  # Create 3 columns per row
                            for j in range(2):
                                idx = i * 2 + j
                                if idx < num_plots:
                                    with cols[j]:  # Place the plot in the respective column
                                        # st.plotly_chart(plots[idx], use_container_width=True, key=f"plotly_charts_{idx}")
                                        plot_key = f"{market}_{idx}"  # Unique key per market and plot index
                                        st.plotly_chart(plots[idx], use_container_width=True, key=plot_key)
                    # num_plots = len(plots)
                    # num_rows = (num_plots // 1) + (1 if num_plots % 1 != 0 else 0)  # Ensure extra row if needed

                    # for i in range(num_rows):
                    #     cols = st.columns(1)  # Create 3 columns per row
                    #     for j in range(1):
                    #         idx = i * 1 + j
                    #         if idx < num_plots:
                    #             with cols[j]:  # Place the plot in the respective column
                    #                 st.plotly_chart(plots[idx], use_container_width=True, key=f"plotly_charts_{idx}")

                
                    # Convert the max reach data to a DataFrame
                    max_reach_df = pd.DataFrame(max_reach_data)
                    st.dataframe(max_reach_df)

                    results_df = pd.DataFrame(results)

                    # Save to Excel in memory
                    excel_file = io.BytesIO()
                    with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:   
                        max_reach_df.to_excel(writer, index=False, sheet_name='Max Reach Data')

                    excel_file.seek(0)

                    # Allow the user to download the file
                    st.download_button(
                        label="Download Max Reach Data",
                        data=excel_file,
                        file_name=f"max_reach_data_{market}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )

                    # Save to Excel in memory
                    excel_file = io.BytesIO()
                    with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:
                        results_df.to_excel(writer, index=False, sheet_name='Reach and Prediction Data')

                    excel_file.seek(0)

                    # Allow the user to download the file
                    st.download_button(
                        label="Download Reach and Prediction Data",
                        data=excel_file,
                        file_name=f"Reach_and_Prediction_Data_{market}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )


                # Plot diminishing return curve
                plot_diminishing_return_curve_with_point(
                    markets=markets, 
                    stacked_data=selected_df, 
                    media_variables=media_variables, 
                    other_variables=other_variables
                )



        # col1,col2=st.columns(2)


        with tab2:


            st.title("Contribution Charts")

            st.markdown(
            """ 
            <div style="height: 2px; background-color: black; margin: 10px 0;"></div>
            """, 
            unsafe_allow_html=True
            )

            
            Contribution_chart_df = df.copy()

            # available_regions = market_weights_df["Region"].unique().tolist()  # Get unique regions
            # # st.markdown(
            # #     '<p style="font-size:15px; color:black; font-weight:bold;">Select a Region:</p>', 
            # #     unsafe_allow_html=True
            # # )
            # selected_region = st.selectbox("Select a Region", available_regions, key="multiselect_regions_contribution_charts")  # Empty label to avoid duplication
            # selected_df = Contribution_chart_df[Contribution_chart_df["Region"]==selected_region]  # Filter data for selected region
            # --- Region selection ---
            available_regions = market_weights_df["Region"].unique().tolist()
            selected_regions = st.multiselect(
                "Select one or more Regions", 
                options=available_regions, 
                default=available_regions,
                key="multiselect_regions_contribution_charts"
            )

            brand = market_weights_df["Brand"].unique()[0]
            # selected_df = selected_df[selected_df["Brand"]==brand]

            

            import numpy as np
            from sklearn.preprocessing import MinMaxScaler, StandardScaler

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
                unique_regions = df["Region"].unique()

                # # Extract media variables dynamically
                # media_variables = [
                #     col.replace('_transformed', '').replace('beta_','')
                #     for col in region_weight_df.columns
                #     if col.endswith('_transformed')  and col.startswith('beta_')
                # ]
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

                # # Add additional media variables
                # additional_media_vars = ['TV_Total_Unique_Reach', 'Digital_Total_Unique_Reach']
                # media_variables += additional_media_vars

                # Filter data by Region and Brand
                filtered_data = {
                region: df[df["Region"] == region].copy() for region in unique_regions
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
                        carryover = 0.5#carryovers[idx_var]
                        # st.write(f"Processing {media_var} with carryover: {carryover}")
                        beta_col = f"{media_var}_adjusted"
                        adstocked = adstock_function(region_df[media_var].values, carryover)
                        region_df[f"{media_var}_Adstock"] = adstocked

                        # Apply carryover/adstock
                        carryover = 0.5#carryovers[idx_var]
                        # st.write(f"Processing {media_var} with carryover: {carryover}")
                        beta_col = f"{media_var}_adjusted"
                        adstocked = adstock_function(region_df[media_var].values, carryover)
                        region_df[f"{media_var}_Adstock(0.5 carryover)"] = adstocked
                        # Apply carryover/adstock
                        carryover = 0.3#carryovers[idx_var]
                        # st.write(f"Processing {media_var} with carryover: {carryover}")
                        beta_col = f"{media_var}_adjusted"
                        adstocked = adstock_function(region_df[media_var].values, carryover)
                        region_df[f"{media_var}_Adstock(0.3 carryover)"] = adstocked

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
                            std_adstock = region_df[f"{media_var}_Adstock"].std()

                            # region_df[f"{media_var}_elasticity"] = (
                            #     beta_value
                            #     * growth_rate
                            #     * region_df[f"{media_var}_Transformed_Base"]
                            #     * (1 - region_df[f"{media_var}_Transformed_Base"])
                            #     * region_df[f"{media_var}"]
                            #     / (std_adstock * region_df["Volume"])
                            # )/(region_df[f"{media_var}_Transformed_Base"].max()-region_df[f"{media_var}_Transformed_Base"].min())

                    # Calculate contributions for other variables
                    for var in other_variables:
                        beta_col = f"beta_scaled_{var}"
                        if beta_col in region_row and f"scaled_{var}" in region_df.columns:
                            beta_value = float(region_row[beta_col])
                            region_df[f"{var}_contribution"] = beta_value * region_df[f"scaled_{var}"]
                            

                    transformed_data_list.append(region_df)

                # Concatenate all transformed data
                transformed_df = pd.concat(transformed_data_list, axis=0).reset_index(drop=True)
                return transformed_df

            all_regions_contribution = []  # List to store processed data for each region

            # --- Loop over each selected region ---
            for selected_region in selected_regions:
                st.subheader(f"📊 Region: {selected_region}")
                import re
                safe_region = re.sub(r'\W+', '_', selected_region)  # safe key for Streamlit widgets

                selected_df = Contribution_chart_df[
                    (Contribution_chart_df["Region"] == selected_region) &
                    (Contribution_chart_df["Brand"] == brand)
                ]

                # Apply transformations with contributions
                transformed_df = apply_transformations_with_contributions(selected_df, market_weights_df)
                transformed_df = transformed_df.fillna(0)


                # Extract media and other variables dynamically
                mainmedia_variables = [col.replace('_adjusted', '') for col in market_weights_df.columns if col.endswith('_adjusted')]
                mediagenre_variables = [col.replace('_adjusted', '') for col in market_weights_df.columns if col.endswith('_adjusted') and "Total" not in col]
                other_variables = [col.replace('beta_scaled_', '') for col in market_weights_df.columns if col.startswith('beta_scaled_')]

                # Combine all variable names used in the model
                mainmedia_model_variables = mainmedia_variables + other_variables
                mediagenre_model_variables = mediagenre_variables + other_variables
                # mediagenre_model_variables
                # st.write(mainmedia_model_variables)


                # Identify contribution columns matching the model variables
                mainmedia_contribution_columns = [
                    col for col in transformed_df.columns
                    if any(col.startswith(var) and col.endswith("_contribution") for var in mainmedia_model_variables)
                ]
                # mainmedia_contribution_columns
                # contribution_columns
                mediagenre_contribution_columns = [
                    col for col in transformed_df.columns
                    if any(col.startswith(var) and col.endswith("_contribution") for var in mediagenre_model_variables)
                ]

                # Compute MainMedia_predY dynamically
                transformed_df["MainMedia_predY"] = transformed_df["beta0"] + transformed_df[mainmedia_contribution_columns].sum(axis=1)

                y = market_weights_df['Y'][0]

                transformed_df["error"] = abs(transformed_df[y] - transformed_df["MainMedia_predY"])/transformed_df[y]

                # Identify contribution columns dynamically (all columns ending with '_contribution')
                contribution_columns = [col for col in transformed_df.columns if col.endswith("_contribution")]

                # Define the base columns that should always be included
                base_columns = ["beta0", "MainMedia_predY",  y]

                # Create the aggregation dictionary dynamically
                agg_dict = {col: "sum" for col in base_columns + contribution_columns}

                # Group by Region and aggregate dynamically
                contribution = transformed_df.groupby(["Region","Fiscal Year"]).agg(agg_dict).reset_index()

                # Extract contribution columns for mainmedia_model_variables
                mainmedia_contribution_columns = [
                    col for col in contribution.columns if any(col.startswith(var) and col.endswith("_contribution") for var in mainmedia_model_variables)
                ]

                # mainmedia_contribution_columns

                # Compute percentage contribution for each mainmedia contribution variable
                for col in mainmedia_contribution_columns:
                    percentage_col = col.replace("_contribution", "_percentage")
                    contribution[percentage_col] = (contribution[col] / contribution["MainMedia_predY"]) * 100

                # Compute base percentage separately
                contribution["beta0_percentage"] = contribution["beta0"] / contribution["MainMedia_predY"] * 100
                # contribution.columns
                # Step 1: Get all percentage columns
                percentage_columns = [col for col in contribution.columns if col.endswith("_percentage")]
                # percentage_columns
                # mainmedia_variables

                # # Step 2: Let user select variables they want to see contribution for
                # media_percentage_columns = st.multiselect(
                #     "Select variables to show contribution for (others will be grouped into Base)",
                #     options=percentage_columns,
                #     default=[f"{var}" for var in percentage_columns if var.startswith("Digital") or var.startswith("TV")]#["TV_Total_Unique_Reach_percentage", "Digital_Total_Unique_Reach_percentage"]  # default can be anything
                # )
                # [f"{var}_percentage" for var in mainmedia_variables if var.startswith("Digital") or var.startswith("TV")]
                # Step 1: First identify all media prefixes dynamically
                media_prefixes = sorted(list(set(
                    col.split('_')[0] for col in mainmedia_variables 
                    #if not any(x in col for x in ['Base', 'beta0', 'Region', 'Intercept'])  # Exclude non-media columns
                )))

                # Step 2: Let user select variables they want to see contribution for
                media_percentage_columns = st.multiselect(
                    "Select variables to show contribution for (others will be grouped into Base)",
                    options=percentage_columns,
                    default=[f"{var}" for var in percentage_columns 
                            if any(var.startswith(prefix) for prefix in media_prefixes)],  # Default all media variables

                    key=f"media_percentage_columns_{selected_region.replace(' ', '_')}"
                )

                # Step 3: Calculate Base percentage using the remaining columns
                base_vars = [col for col in percentage_columns if col not in media_percentage_columns]

                contribution["Base_percentage"] = contribution[base_vars].sum(axis=1)

                # Columns to plot
                plot_columns = ["Base_percentage"] + media_percentage_columns
                # st.dataframe(contribution)
                # Keep only required columns
                final_cols = ["Region", "Brand", "Fiscal Year"] + percentage_columns + ["Base_percentage"]
                contribution["Brand"] = brand  # add brand column
                all_regions_contribution.append(contribution[final_cols])


                import streamlit as st
                import pandas as pd
                import plotly.express as px

                # Sample DataFrame (Replace with actual 'contribution' DataFrame)
                # contribution = pd.read_csv("your_data.csv")

                # Assume the region is already selected, so get the unique region from the data
                selected_region = contribution["Region"].unique()[0]  # Default to the first region or use a predefined value

                # Add extra space between dropdown and pie chart
                # st.markdown("<br>", unsafe_allow_html=True)  # Adds two blank liness

                # Select Fiscal Year - Dropdown above the charts
                selected_fiscal_year = st.selectbox("Select Fiscal Year", contribution["Fiscal Year"].unique(), key=f"fiscal_year_{selected_region.replace(' ', '_')}")  # Unique key per region

                # Filter data based on selection
                filtered_data = contribution[(contribution["Region"] == selected_region) & 
                                            (contribution["Fiscal Year"] == selected_fiscal_year)]

                if not filtered_data.empty:
                    # Pie chart data
                    values = filtered_data[plot_columns].values.flatten()
                    labels = ["Other Factors"]+[col.replace("_percentage", "").replace("_", " ").title() for col in media_percentage_columns]#,"TV Reach", "Digital Reach"]   #["Base"] + media_percentage_columns  # Rename Base and keep media labels
                    

                    # Create Plotly Pie Chart with Custom Styling
                    fig = px.pie(
                        names=labels,
                        values=values,
                        title=f"Contribution Chart for {selected_region} - {selected_fiscal_year}",
                        hole=0.3,  # Donut-style
                        color_discrete_sequence=px.colors.sequential.Purp,  # Custom color scheme
                    )

                    # Customize labels, font size, and layout
                    fig.update_traces(
                        textinfo="percent+label",  # Show both percentage and labels
                        textfont_size=16,  # Adjust font size
                        pull=[0.05 if label == "Other Factors" else 0 for label in labels],  # Slightly pull "Base" slice out
                        insidetextfont=dict(color="black"),  # Set inside text color to black
                        outsidetextfont=dict(color="black")  # Set outside text color to black
                    )

                    # Update overall layout to prevent overlap
                    fig.update_layout(
                        title_font_size=18,
                        title_font_family="Arial",
                        title_x=0.5,  # Center-align title
                        showlegend=False,  # Hide legend
                        margin=dict(l=40, r=40, t=200, b=40),  # Increase top margin
                        height=600,  # Reduce overall figure height
                    )

                    # Show the chart in Streamlit
                    st.plotly_chart(fig)

                else:
                    st.warning(f"No data available for {selected_region} - {selected_fiscal_year}.")

                # Concatenate all regions & FYs
                final_contribution_df = pd.concat(all_regions_contribution, ignore_index=True)

                # Identify numerical columns (exclude Region, Brand, Fiscal Year)
                num_cols = final_contribution_df.select_dtypes(include='number').columns

                # Divide all numerical columns by 100
                final_contribution_df[num_cols] = final_contribution_df[num_cols] / 100

                # Preview in Streamlit
                # st.dataframe(final_contribution_df)


        with tab3:

            st.title("Waterfall Charts")
            st.markdown(
            """ 
            <div style="height: 2px; background-color: black; margin: 10px 0;"></div>
            """, 
            unsafe_allow_html=True
            )

            # Add extra space between dropdown and pie chart
            st.markdown("<br><br>", unsafe_allow_html=True)  # Adds two blank liness

            waterfall_chart_df = df.copy()

            available_regions = market_weights_df["Region"].unique().tolist()  # Get unique regions
            # st.markdown(
            #     '<p style="font-size:15px; color:black; font-weight:bold;">Select a Region:</p>', 
            #     unsafe_allow_html=True
            # )
            # selected_region = st.selectbox("Select a Region", available_regions, key="multiselect_regions_waterfall_charts")  # Empty label to avoid duplication
            selected_df = waterfall_chart_df[waterfall_chart_df["Region"].isin(available_regions)]  # Filter data for selected region
            brand = market_weights_df["Brand"].unique()[0]
            selected_df = selected_df[selected_df["Brand"]==brand]
            # st.write(selected_df["Region"].unique())
            # Apply transformations with contributions
            # st.dataframe(market_weights_df)
            transformed_df = apply_transformations_with_contributions(selected_df, market_weights_df)
            transformed_df = transformed_df.fillna(0)
            # st.dataframe(
            #     transformed_df.groupby("Region")
            #     .sum(numeric_only=True)
            #     .reset_index()
            # )

            # Define the base columns that should always be included
            base_columns = [y]

            other_variables = [col.replace('beta_scaled_', 'scaled_') for col in market_weights_df.columns if col.startswith('beta_scaled_')]
            # other_variables

            # Combine all variable names used in the model
            mainmedia_model_variables = mainmedia_variables + other_variables
            # mainmedia_model_variables

            mainmedia_contribution_columns = [
                col for col in transformed_df.columns
                if any(col.startswith(var) and col.endswith("_transformed") for var in mainmedia_model_variables)
            ]
            # mainmedia_contribution_columns

            # Create the aggregation dictionary dynamically
            agg_dict = {col: "sum" for col in base_columns +other_variables+ mainmedia_contribution_columns}
            # agg_dict

            group = transformed_df.groupby(["Region","Fiscal Year"]).agg(agg_dict).reset_index()
            # group
            
            
            # Get unique fiscal years from the data
            unique_fiscal_years = sorted(group["Fiscal Year"].unique())
            # st.write("Contribution df", contribution )

            # Fiscal Year Selection
            col1, col2 = st.columns(2)
            with col1:
                fy_from = st.selectbox("Select From Fiscal Year:", unique_fiscal_years, index=0)
            with col2:
                fy_to = st.selectbox("Select To Fiscal Year:", unique_fiscal_years, index=len(unique_fiscal_years)-1)

            # Ensure the selection is valid
            if fy_from == fy_to:
                st.warning("Please select two different fiscal years.")
            elif fy_from > fy_to:
                st.warning("The 'From' fiscal year should be earlier than the 'To' fiscal year.")
            else:
                # Pivot to have Fiscal Years as columns for easier calculation
                pivot_contribution = group.pivot(index="Region", columns="Fiscal Year")

                # Check if both selected fiscal years exist in the dataset
                if fy_from in pivot_contribution.columns.levels[1] and fy_to in pivot_contribution.columns.levels[1]:
                    # Calculate the difference between the selected fiscal years
                    difference = pivot_contribution.xs(fy_to, level=1, axis=1) - pivot_contribution.xs(fy_from, level=1, axis=1)

                    # Add a Fiscal Year column for difference rows and reset index
                    difference["Fiscal Year"] = f"{fy_to}-{fy_from}"
                    difference.reset_index(inplace=True)

                    # Display the calculated difference
                    # st.dataframe(difference)

                    # (Optional) Add a waterfall chart visualization here
                else:
                    st.warning("Selected fiscal years are not available in the dataset.")

            # Melt difference back to long format and add it to the original contribution DataFrame
            difference_long = difference.melt(id_vars=["Region", "Fiscal Year"], var_name="Variable", value_name="Value")
            contribution_long = group.melt(id_vars=["Region", "Fiscal Year"], var_name="Variable", value_name="Value")

            # Combine original data and the differences
            final_contribution = pd.concat([contribution_long, difference_long], ignore_index=True)
            final_contribution["Value"] = pd.to_numeric(final_contribution["Value"], errors="coerce")
            # st.write("Final Contribution Data:")
            # st.write(final_contribution)


            # Pivot final data to create a waterfall-friendly structure
            waterfall_data = final_contribution.pivot_table(index=["Region", "Fiscal Year"], columns="Variable", values="Value").reset_index()
            # st.write("Waterfall Data:")
            # st.write(waterfall_data)

            base_columns = [ 'Region', 'beta0' ]

            other_variables = [col.replace('beta_scaled_', 'beta_scaled_') for col in market_weights_df.columns if col.startswith('beta_scaled_')]
            # other_variables
            media_variables = [col.replace('_adjusted', '_adjusted') for col in market_weights_df.columns if col.endswith('_adjusted')]

            # Combine all variable names used in the model
            mainmedia_model_variables = base_columns + other_variables + media_variables
            # mainmedia_model_variables
            relevant_betas = mainmedia_model_variables


            # selected_region = contribution["Region"].unique()[0]
            # st.write(selected_region)
            # region_weights_df = market_weights_df[market_weights_df["Region"]==selected_region]
            region_weights_df = market_weights_df.copy()
            # Keep only relevant columns in region_weights_df
            region_weights_filtered = region_weights_df[relevant_betas]

            # Generate rename mapping dynamically based on patterns
            rename_mapping = {
                col: col.replace("beta_scaled_", "scaled_") if col.startswith("beta_scaled_") else col.replace("_adjusted", "_transformed")
                for col in region_weights_filtered.columns
                if col.startswith("beta_scaled_") or col.endswith("_adjusted")
            }

            # Rename columns in region_weights_filtered
            region_weights_filtered.rename(columns=rename_mapping, inplace=True)

            # Optional: Display the mapping to verify
            # st.write("Column Rename Mapping:", rename_mapping)

            # st.dataframe(region_weights_filtered)
            # st.dataframe(waterfall_data)
            #  For row-wise concatenation:
            concatenated_data = pd.concat([waterfall_data, region_weights_filtered], axis=0, ignore_index=True)
            # st.dataframe(concatenated_data)

            concatenated_data["Fiscal Year"] = concatenated_data["Fiscal Year"].fillna("Coefficient")


            other_variables = [col.replace('beta_scaled_', 'scaled_') for col in market_weights_df.columns if col.startswith('beta_scaled_')]
            # other_variables
            media_variables = [col.replace('_adjusted', '_transformed') for col in market_weights_df.columns if col.endswith('_adjusted')]

            relevant_vars = other_variables + media_variables


            # Filter rows for FY24-FY23 differences and coefficients for each region
            impact_rows = []
            for region in concatenated_data["Region"].unique():
                # Extract rows for the current region
                region_data = concatenated_data[concatenated_data["Region"] == region]
                
                # Separate FY24-FY23 difference row and coefficient row
                fy_difference_row = region_data[region_data["Fiscal Year"] == f"{fy_to}-{fy_from}"]
                coefficients_row = region_data[region_data["Fiscal Year"] == "Coefficient"]
                # st.write(coefficients_row, fy_difference_row)
                
                if not fy_difference_row.empty and not coefficients_row.empty:
                    # Multiply differences by coefficients for relevant variables
                    impact_values = {
                        var: fy_difference_row[var].values[0] * coefficients_row[var].values[0]
                        for var in relevant_vars
                    }
                    
                    # Sum the contributions for total impact
                    total_impact = sum(impact_values.values())
                    
                    # Create a new row for FY24-FY23 Impact
                    impact_row = {"Region": region, "Fiscal Year": f"{fy_to}-{fy_from} Impact", **impact_values, "Total_Impact": total_impact}
                    impact_rows.append(impact_row)

            # Convert the list of impact rows to a DataFrame
            impact_df = pd.DataFrame(impact_rows)

            # Add the impact rows to the original concatenated data
            final_data = pd.concat([concatenated_data, impact_df], ignore_index=True)

            # Stack data by Market
            final_data = final_data.groupby("Region").apply(lambda x: x).reset_index(drop=True)

            base_var = ["Region","Fiscal Year","beta0"]
            final_data = final_data[base_var+[y]+media_variables+other_variables]
            # final_data.columns
            
            #     return waterfall_data
            # Let the user select transformed variables for the waterfall chart
            transformed_columns = [col for col in final_data.columns if col.endswith("_transformed") or col.startswith("scaled_")]
            # transformed_columns
            selected_waterfall_vars = st.multiselect(
                "Select variables for waterfall chart", 
                options=transformed_columns,
                default=[col for col in final_data.columns if col.endswith("_transformed")]
            )


            def generate_waterfall_data(region, region_data):
                waterfall_data = []

                # FY23 volume
                fy23_filtered_volume = region_data[region_data['Fiscal Year'] == f'{fy_from}'][y].sum()
                waterfall_data.append([region, f'{fy_from}', fy23_filtered_volume, 100])  # base = 100%

                # FY24 volume
                fy24_filtered_volume = region_data[region_data['Fiscal Year'] == f'{fy_to}'][y].sum()

                # Impact year data (e.g., FY24-FY23 Impact)
                impact_df = region_data[region_data['Fiscal Year'] == f'{fy_to}-{fy_from} Impact']

                # Total change
                total_change = fy24_filtered_volume - fy23_filtered_volume
                total_change_abs = abs(total_change)

                # Track sum of selected impacts
                total_selected_impact = 0

                # Loop through selected variables and compute impact
                for var in selected_waterfall_vars:
                    var_name = var.replace("_transformed", "").replace("scaled_", "").replace("_", " ")
                    impact = impact_df[var].sum()
                    # st.write(f"Impact for {var_name} in {region}: {impact}")
                    percentage = (impact / total_change_abs) * 100 if total_change_abs != 0 else 0
                    waterfall_data.append([region, var_name, impact, percentage])
                    total_selected_impact += impact

                # Base/Other impact
                base_impact = total_change - total_selected_impact
                base_percentage = (base_impact / total_change_abs) * 100 if total_change_abs != 0 else 0
                waterfall_data.append([region, 'Other Factors', base_impact, base_percentage])

                # FY24 percentage relative to FY23
                fy24_percentage = (fy24_filtered_volume / fy23_filtered_volume) * 100 if fy23_filtered_volume != 0 else 0
                waterfall_data.append([region, f'{fy_to}', fy24_filtered_volume, fy24_percentage])

                return waterfall_data


            # Initialize an empty list to store all regions' waterfall data
            waterfall_data_list = []

            # Loop through each region and generate data
            regions = final_data['Region'].unique()
            for region in regions:
                region_data = final_data[final_data['Region'] == region]
                waterfall_data_list.extend(generate_waterfall_data(region, region_data))

            # Convert list to DataFrame
            waterfall_df = pd.DataFrame(waterfall_data_list, columns=['Region', 'Variables', 'Absolute Contribution', 'Percentage Contribution'])
            # waterfall_df

            import streamlit as st
            import plotly.graph_objects as go
            import plotly.io as pio

            # Set the default renderer to browser (use this if running outside of a Jupyter notebook)
            pio.renderers.default = "browser"

            # Loop through each region and create a waterfall chart
            for region in waterfall_df['Region'].unique():
                region_data = waterfall_df[waterfall_df['Region'] == region]

                # Define measure values: "relative" for intermediate bars, "total" for FY23 and FY24
                measure_values = ["absolute"] + ["relative"] * (len(region_data) - 2) + ["absolute"]

                # Create the Waterfall Chart
                fig = go.Figure(go.Waterfall(
                    x=region_data['Variables'],  # X-axis: Variables
                    y=region_data['Percentage Contribution'],  # Y-axis: Percentage Contribution
                    text=region_data['Percentage Contribution'].round(0).astype(str) + '%',  # Add labels
                    textposition="outside", 
                    insidetextfont=dict(family="Arial", size=14, color="black"),  # Black text inside bars
                    outsidetextfont=dict(family="Arial", size=14, color="black"),  # Black text outside bars 
                    measure=measure_values,  # Make FY24 a total bar
                    decreasing={"marker": {"color": "#FFA500"}},  # Red for negative impacts
                    increasing={"marker": {"color": "#32CD32"}},  # Green for positive impacts
                    totals={"marker": {"color": "#4169E1"}}  # Blue for FY23 and FY24
                ))

                # Customize Layout
                fig.update_layout(
                    title=dict(
                        text=f'Waterfall Chart for {region}',
                        font=dict(size=20)  # Increase title font size (adjust as needed)
                    ),
                    xaxis_title="Variables",
                    yaxis_title="Percentage Contribution (%)",
                    showlegend=False,
                    height=550
                )

                # Adjust the y-axis range to fit the chart properly
                fig.update_yaxes(range=[0, 350])  # Add some extra space above the highest value

                # Display the chart in Streamlit
                st.plotly_chart(fig,key=f"waterfall_chart_{region}_{fy_from}_{fy_to}")


                import streamlit as st
                import pandas as pd
                import plotly.express as px

                
                # st.plotly_chart(fig)
                # FY filter based on selected years
                filtered_df = transformed_df[transformed_df["Fiscal Year"].isin([fy_from, fy_to])]
                filtered_df = filtered_df[filtered_df["Region"] == region]

                # Group by Region and Fiscal Year, summing over selected variables
                group_cols = ["Region", "Fiscal Year"]
                grouped_df = filtered_df[group_cols + selected_waterfall_vars].groupby(group_cols).sum().reset_index()
                # grouped_df

                # Pivot: index is Region, columns are (variable, FY)
                pivot_df = grouped_df.pivot(index="Region", columns="Fiscal Year", values=selected_waterfall_vars)

                # Rename columns to be clean like TV_FY23, TV_FY24, etc.
                pivot_df.columns = [f"{col.replace('_transformed','').replace('scaled_','')}_{fy}" for col, fy in pivot_df.columns]
                pivot_df = pivot_df.reset_index()

                # Compute percentage change for each variable
                for var in selected_waterfall_vars:
                    clean_var = var.replace("_transformed", "").replace("scaled_", "")
                    fy23_col = f"{clean_var}_{fy_from}"
                    fy24_col = f"{clean_var}_{fy_to}"
                    percent_change_col = f"{clean_var}_Percent_Change"
                    pivot_df[percent_change_col] = ((pivot_df[fy24_col] - pivot_df[fy23_col]) / pivot_df[fy23_col]) * 100

                # Melt for plotting
                percent_change_cols = [col for col in pivot_df.columns if col.endswith("_Percent_Change")]
                melted_df = pivot_df.melt(
                    id_vars=["Region"],
                    value_vars=percent_change_cols,
                    var_name="Media Type",
                    value_name="Percentage Change"
                )

                # Clean the Media Type names for display
                melted_df["Media Type"] = melted_df["Media Type"].str.replace("_Percent_Change", "").str.replace("_", " ")

                # # Plot
                # fig = px.bar(
                #     melted_df,
                #     x="Region",
                #     y="Percentage Change",
                #     # color_discrete_sequence=["#636EFA"],
                #     color="Media Type",
                #     barmode="group",
                #     title=f"Percentage Change in Selected Variables ({fy_to} vs {fy_from})",
                #     labels={"Percentage Change": "% Change"},
                #     text_auto=True
                # )

                # st.plotly_chart(fig)

                import plotly.express as px
                import plotly.colors as pc

                # Get unique items (e.g., Media Types or Regions)
                unique_values = melted_df["Media Type"].unique()

                # Generate different shades of the same color
                shades = px.colors.sequential.Darkmint[-len(unique_values):]  # Take last N shades (darker to lighter)

                # Map each Media Type to a shade
                color_map = dict(zip(unique_values, shades))

                # # Plot using the color map
                # fig = px.bar(
                #     melted_df,
                #     x="Region",
                #     y="Percentage Change",
                #     color="Media Type",
                #     color_discrete_map=color_map,
                #     barmode="group",
                #     title=f"Percentage Change in Selected Variables ({fy_to} vs {fy_from})",
                #     labels={"Percentage Change": "% Change"},
                #     text_auto=True
                # )

                # st.plotly_chart(fig)


                    # Create empty columns to shift the chart to the right
                col1, col2, _ = st.columns([0.015,1,0.13])  # Adjust the ratio as needed

                with col2:  # Place the chart in the second column to shift it right

                    # Plotly bar chart
                    fig = px.bar(melted_df, 
                                x="Region", 
                                y="Percentage Change", 
                                color="Media Type", 
                                barmode="group",
                                color_discrete_map=color_map,
                                # title="Percentage Change in TV & Digital Reach & KPI (FY24 vs FY23)",
                                labels={"Percentage Change": "% Change"},
                                text=melted_df["Percentage Change"].round(2).astype(str) + '%',
                                # width=420,  # Adjust width as needed
                                # height=350)   # Adjust height as needed
                                )
                    
                    # Remove legend
                    fig.update_layout(showlegend=False)

                    # Add spacing between bar groups and within bar groups
                    fig.update_layout(
                        bargap=0.25,         # space between bar groups (0 to 1)
                        bargroupgap=0.2      # space between bars within the same group
                    )

                    # Display in Streamlit
                    st.plotly_chart(fig,key=f"percentage_change_bar_chart_{region}_{fy_from}_{fy_to}")