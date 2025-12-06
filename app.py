import streamlit as st
import pandas as pd
from datetime import date

# ---------- Data loading ----------

@st.cache_data
def load_data():
    base_path = "."

    suppliers = pd.read_csv(f"{base_path}/suppliers.csv")
    shippers = pd.read_csv(f"{base_path}/shippers.csv")
    products = pd.read_csv(f"{base_path}/products.csv")
    orders = pd.read_csv(f"{base_path}/orders.csv")
    order_details = pd.read_csv(f"{base_path}/order_details.csv")
    employees = pd.read_csv(f"{base_path}/employees.csv")
    customers = pd.read_csv(f"{base_path}/customers.csv")
    categories = pd.read_csv(f"{base_path}/categories.csv")

    # Parse dates
    orders["OrderDate"] = pd.to_datetime(orders["OrderDate"])

    # Build fact table: one row per order line
    df = (
        order_details
        .merge(products, on="ProductID", how="left")
        .merge(orders, on="OrderID", how="left")
        .merge(customers, on="CustomerID", how="left")
        .merge(categories, on="CategoryID", how="left")
        .merge(suppliers, on="SupplierID", how="left")
        .merge(shippers, on="ShipperID", how="left")
    )

    df["LineRevenue"] = df["Quantity"] * df["Price"]

    return df


df = load_data()

st.set_page_config(
    page_title="Sales Dashboard",
    layout="wide"
)

st.title("Sales Dashboard: Orders, Customers & Products")

# ---------- Filters ----------

st.sidebar.header("Filters")

# Date range filter
min_date = df["OrderDate"].min().date()
max_date = df["OrderDate"].max().date()

start_date, end_date = st.sidebar.date_input(
    "Date range",
    (min_date, max_date),
    min_value=min_date,
    max_value=max_date
)

if not isinstance(start_date, date):
    start_date, end_date = min_date, max_date

mask_date = (df["OrderDate"].dt.date >= start_date) & (df["OrderDate"].dt.date <= end_date)

# Category filter (safe: only if CategoryName exists)
if "CategoryName" in df.columns:
    all_categories = sorted(df["CategoryName"].dropna().unique())
    category_filter = st.sidebar.multiselect("Category", all_categories, default=all_categories)
    mask_cat = df["CategoryName"].isin(category_filter) if category_filter else True
else:
    mask_cat = True

filtered = df[mask_date & mask_cat].copy()

# ---------- KPI cards ----------

st.subheader("Key Metrics")

if filtered.empty:
    st.warning("No data for the selected filters. Try expanding the date range or filters.")
else:
    total_revenue = filtered["LineRevenue"].sum()
    num_orders = filtered["OrderID"].nunique()
    num_customers = filtered["CustomerID"].nunique()
    avg_order_value = filtered.groupby("OrderID")["LineRevenue"].sum().mean()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Revenue", f"${total_revenue:,.0f}")
    col2.metric("Orders", f"{num_orders:,}")
    col3.metric("Customers", f"{num_customers:,}")
    col4.metric("Avg Order Value", f"${avg_order_value:,.0f}")

# ---------- Charts row 1: Time-series & Category mix ----------

if not filtered.empty:
    st.markdown("---")
    col_ts, col_cat = st.columns([2, 1])

    with col_ts:
        st.subheader("Revenue by Month")

        monthly = (
            filtered
            .set_index("OrderDate")
            .resample("M")["LineRevenue"]
            .sum()
            .reset_index()
        )
        monthly["YearMonth"] = monthly["OrderDate"].dt.to_period("M").astype(str)

        st.line_chart(
            monthly.set_index("YearMonth")["LineRevenue"],
            height=300
        )

    with col_cat:
        st.subheader("Revenue by Category")

        if "CategoryName" in filtered.columns:
            cat_rev = (
                filtered
                .groupby("CategoryName", as_index=False)["LineRevenue"]
                .sum()
                .sort_values("LineRevenue", ascending=False)
            )

            st.bar_chart(
                cat_rev.set_index("CategoryName")["LineRevenue"],
                height=300
            )
        else:
            st.info("Category data not available in this dataset.")

# ---------- Charts row 2: Top customers ----------

if not filtered.empty:
    st.markdown("---")
    st.subheader("Top 10 Customers by Revenue")

    if "CustomerName" in filtered.columns:
        cust_rev = (
            filtered
            .groupby("CustomerName", as_index=False)["LineRevenue"]
            .sum()
            .sort_values("LineRevenue", ascending=False)
            .head(10)
        )

        st.bar_chart(
            cust_rev.set_index("CustomerName")["LineRevenue"],
            height=300
        )
    else:
        st.info("Customer names not available in this dataset.")

# ---------- Customer table ----------

st.markdown("---")
st.subheader("Customer Details")

if not filtered.empty and "CustomerID" in filtered.columns:
    cust_summary = (
        filtered
        .groupby(["CustomerID"], as_index=False)
        .agg(
            Revenue=("LineRevenue", "sum"),
            Orders=("OrderID", "nunique")
        )
    )

    if "CustomerName" in filtered.columns:
        # get a mapping from CustomerID to name
        name_map = (
            filtered[["CustomerID", "CustomerName"]]
            .drop_duplicates()
            .set_index("CustomerID")["CustomerName"]
            .to_dict()
        )
        cust_summary["CustomerName"] = cust_summary["CustomerID"].map(name_map)

    cust_summary["AvgOrderValue"] = cust_summary["Revenue"] / cust_summary["Orders"]

    st.dataframe(
        cust_summary.sort_values("Revenue", ascending=False),
        use_container_width=True
    )
else:
    st.info("Customer-level data not available for the current filters.")

# ---------- Raw data expander ----------

with st.expander("Show raw line-level data"):
    st.dataframe(filtered.head(500), use_container_width=True)

