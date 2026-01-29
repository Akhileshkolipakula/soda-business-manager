# app.py
import streamlit as st
import pandas as pd
import sqlite3
from datetime import date
import plotly.express as px
import os

# -------------------- CONFIG --------------------
st.set_page_config(page_title="Soda Business Manager", layout="wide")
APP_PASSWORD = "soda123"

# -------------------- RERUN / REFRESH HELPERS --------------------
def run_rerun():
    """
    Trigger a full page rerun to refresh data immediately.
    """
    st.rerun()

# -------------------- AUTH (PERSISTENT) --------------------
AUTH_FILE = "auth_session.txt"


def is_logged_in():
    if os.path.exists(AUTH_FILE):
        with open(AUTH_FILE, "r") as f:
            return f.read().strip() == "1"
    return False


def set_login(state: bool):
    with open(AUTH_FILE, "w") as f:
        f.write("1" if state else "0")


# Load login state on refresh
if "authenticated" not in st.session_state:
    st.session_state.authenticated = is_logged_in()


if not st.session_state.authenticated:
    st.title("🔐 Soda Business Manager Login")

    with st.form("login_form"):
        pwd = st.text_input("Enter password", type="password")
        submitted = st.form_submit_button("Login")

        if submitted:
            if pwd == APP_PASSWORD:
                st.session_state.authenticated = True
                set_login(True)   # ✅ Save login
                st.success("Login successful")
                st.rerun()
            else:
                st.error("Wrong password")

    st.stop()

# Keep page in session state so we can programmatically change it
if "page" not in st.session_state:
    st.session_state.page = "Dashboard"

if not st.session_state.authenticated:
    st.title("🔐 Soda Business Manager Login")
    with st.form("login_form"):
        pwd = st.text_input("Enter password", type="password")
        submitted = st.form_submit_button("Login")
        if submitted:
            if pwd == APP_PASSWORD:
                st.session_state.authenticated = True
                # set page to Dashboard and rerun so sidebar reflects it immediately
                st.session_state.page = "Dashboard"
                run_rerun()
            else:
                st.error("Wrong password")
    st.stop()

# -------------------- DATABASE --------------------
DB_PATH = os.path.join(os.path.dirname(__file__), "soda_business.db")
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
c = conn.cursor()

# -------------------- TABLES --------------------
c.executescript("""
CREATE TABLE IF NOT EXISTS flavors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    flavor_name TEXT UNIQUE
);

CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    flavor_id INTEGER,
    cost_price REAL,
    selling_price REAL,
    stock INTEGER,
    FOREIGN KEY(flavor_id) REFERENCES flavors(id)
);

CREATE TABLE IF NOT EXISTS stock_additions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER,
    date TEXT,
    quantity INTEGER,
    batch_cost REAL,
    FOREIGN KEY(product_id) REFERENCES products(id)
);

CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    phone TEXT,
    shop_name TEXT,
    area TEXT
);

CREATE TABLE IF NOT EXISTS sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER,
    date TEXT,
    quantity INTEGER,
    revenue REAL,
    customer_id INTEGER,
    FOREIGN KEY(product_id) REFERENCES products(id),
    FOREIGN KEY(customer_id) REFERENCES customers(id)
);

CREATE TABLE IF NOT EXISTS investments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT,
    amount REAL,
    note TEXT
);
""")
conn.commit()

# -------------------- HELPERS --------------------
def get_flavors():
    df = pd.read_sql("SELECT * FROM flavors ORDER BY flavor_name", conn)
    if "flavor_name" in df.columns:
        df["flavor_name"] = df["flavor_name"].fillna("Unknown flavor")
    return df

def get_products():
    df = pd.read_sql("""
        SELECT p.id, p.flavor_id, p.cost_price, p.selling_price, p.stock, f.flavor_name
        FROM products p
        LEFT JOIN flavors f ON p.flavor_id = f.id
        ORDER BY f.flavor_name, p.id
    """, conn)
    if "flavor_name" in df.columns:
        df["flavor_name"] = df["flavor_name"].fillna("Unknown flavor")
    if "stock" in df.columns:
        df["stock"] = df["stock"].fillna(0).astype(int)
    if "cost_price" in df.columns:
        df["cost_price"] = df["cost_price"].fillna(0.0).astype(float)
    if "selling_price" in df.columns:
        df["selling_price"] = df["selling_price"].fillna(0.0).astype(float)
    return df

def get_customers():
    df = pd.read_sql("SELECT * FROM customers ORDER BY name", conn)
    return df

# ensure helpers re-evaluate when refresh flag toggles
_ = st.session_state.get("_refresh_flag", False)

# -------------------- SIDEBAR --------------------
st.sidebar.title("🥤 Soda Manager")
# bind radio to session_state so we can change it programmatically
page = st.sidebar.radio(
    "Navigation",
    [
        "Dashboard",
        "Flavors",
        "Products",
        "Add Stock",
        "Record Sale",
        "Company Investment",
        "Reports & Graphs",
        "Financial Summary",
        "Customers"
    ],
    index=["Dashboard","Flavors","Products","Add Stock","Record Sale","Company Investment","Reports & Graphs","Financial Summary","Customers"].index(st.session_state.get("page","Dashboard")),
    key="page"
)

# -------------------- DASHBOARD --------------------
if page == "Dashboard":
    st.title("📊 Dashboard")
    products = get_products()

    total_stock = int(products["stock"].sum()) if not products.empty else 0
    total_revenue_row = pd.read_sql("SELECT COALESCE(SUM(revenue), 0) AS r FROM sales", conn)
    total_revenue = float(total_revenue_row["r"].iloc[0]) if not total_revenue_row.empty else 0.0
    total_investment_row = pd.read_sql("SELECT COALESCE(SUM(amount), 0) AS a FROM investments", conn)
    total_investment = float(total_investment_row["a"].iloc[0]) if not total_investment_row.empty else 0.0

    # Cost Used = total production cost incurred (sum of batch_cost from stock_additions)
    cost_used_row = pd.read_sql("""
        SELECT COALESCE(SUM(batch_cost), 0) AS cost_used
        FROM stock_additions
    """, conn)
    cost_used = float(cost_used_row["cost_used"].iloc[0]) if not cost_used_row.empty else 0.0

    remaining_investment = total_investment - cost_used
    profit = total_revenue - cost_used

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Stock", total_stock)
    c2.metric("Revenue", f"₹{total_revenue:,.2f}")
    c3.metric("Cost Used (Production)", f"₹{cost_used:,.2f}")
    c4.metric("Remaining Investment", f"₹{remaining_investment:,.2f}")
    c5.metric("Profit / Loss", f"₹{profit:,.2f}")

    st.subheader("📦 Stock Table")
    if not products.empty:
        st.dataframe(products[["flavor_name", "cost_price", "selling_price", "stock"]], use_container_width=True)
        
        low = products[products["stock"] < 10]
        if not low.empty:
            st.subheader("⚠️ Low Stock Alert")
            st.dataframe(low[["flavor_name", "stock"]], use_container_width=True)
    else:
        st.info("No products added yet.")

# -------------------- FLAVORS --------------------
elif page == "Flavors":
    st.title("🧃 Manage Flavors")
    flavors = get_flavors()
    with st.form("add_flavor"):
        new_flavor = st.text_input("Flavor Name")
        if st.form_submit_button("Add Flavor"):
            if new_flavor and new_flavor.strip():
                try:
                    c.execute("INSERT INTO flavors(flavor_name) VALUES (?)", (new_flavor.strip(),))
                    conn.commit()
                    st.success("Flavor added")
                    run_rerun()
                except sqlite3.IntegrityError:
                    st.error("Flavor already exists")
            else:
                st.error("Enter flavor name")

    if not flavors.empty:
        for _, row in flavors.iterrows():
            col1, col2, col3 = st.columns([3,2,1])
            col1.write(row["flavor_name"])
            if col2.button("✏️ Edit", key=f"edit_flavor_{row['id']}"):
                st.session_state.edit_flavor_id = int(row["id"])
            if col3.button("🗑", key=f"del_flavor_{row['id']}"):
                c.execute("DELETE FROM flavors WHERE id=?", (int(row["id"]),))
                conn.commit()
                st.success("Flavor deleted")
                run_rerun()
        if "edit_flavor_id" in st.session_state:
            fid = st.session_state.edit_flavor_id
            flavor_row = flavors[flavors["id"]==fid].iloc[0]
            with st.form("edit_flavor"):
                new_name = st.text_input("Flavor Name", flavor_row["flavor_name"])
                if st.form_submit_button("Update Flavor"):
                    c.execute("UPDATE flavors SET flavor_name=? WHERE id=?", (new_name.strip(), fid))
                    conn.commit()
                    st.success("Flavor updated")
                    del st.session_state.edit_flavor_id
                    run_rerun()
    else:
        st.info("No flavors added yet.")

# -------------------- PRODUCTS --------------------
elif page == "Products":
    st.title("🛒 Manage Products")
    flavors = get_flavors()
    products = get_products()
    if flavors.empty:
        st.warning("Add flavors first")
        st.stop()

    with st.form("add_product"):
        flavor_options = flavors[["id","flavor_name"]].to_dict(orient="records")
        flavor_choice = st.selectbox("Select Flavor", options=flavor_options, format_func=lambda x: x["flavor_name"])
        cost = st.number_input("Cost Price", min_value=0.0, format="%.2f")
        price = st.number_input("Selling Price", min_value=0.0, format="%.2f")
        stock = st.number_input("Initial Stock", min_value=0, step=1, value=0)
        if st.form_submit_button("Add Product"):
            flavor_id = int(flavor_choice["id"])
            c.execute("INSERT INTO products(flavor_id, cost_price, selling_price, stock) VALUES (?,?,?,?)",
                      (flavor_id, float(cost), float(price), int(stock)))
            conn.commit()
            st.success("Product added")
            run_rerun()

    if not products.empty:
        for _, row in products.iterrows():
            col1,col2,col3,col4,col5,col6 = st.columns([3,2,2,2,2,1])
            col1.write(row["flavor_name"])
            col2.write(f"₹{row['cost_price']:.2f}")
            col3.write(f"₹{row['selling_price']:.2f}")
            col4.write(f"Stock: {int(row['stock'])}")
            if col5.button("✏️ Edit", key=f"edit_prod_{row['id']}"):
                st.session_state.edit_product_id = int(row["id"])
            if col6.button("🗑", key=f"del_prod_{row['id']}"):
                c.execute("DELETE FROM products WHERE id=?", (int(row["id"]),))
                conn.commit()
                st.success("Product deleted")
                run_rerun()
        if "edit_product_id" in st.session_state:
            pid = st.session_state.edit_product_id
            prod = products[products["id"]==pid].iloc[0]
            with st.form("edit_product"):
                flavor_list = flavors[["id","flavor_name"]].to_dict(orient="records")
                default_index = 0
                for i, f in enumerate(flavor_list):
                    if int(f["id"]) == int(prod["flavor_id"]):
                        default_index = i
                        break
                flavor_choice = st.selectbox("Flavor", options=flavor_list, index=default_index, format_func=lambda x: x["flavor_name"])
                cost = st.number_input("Cost Price", value=float(prod["cost_price"]), format="%.2f")
                price = st.number_input("Selling Price", value=float(prod["selling_price"]), format="%.2f")
                stock = st.number_input("Stock", value=int(prod["stock"]), step=1)
                if st.form_submit_button("Update Product"):
                    flavor_id = int(flavor_choice["id"])
                    c.execute("UPDATE products SET flavor_id=?, cost_price=?, selling_price=?, stock=? WHERE id=?",
                              (flavor_id, float(cost), float(price), int(stock), pid))
                    conn.commit()
                    st.success("Product updated")
                    del st.session_state.edit_product_id
                    run_rerun()
    else:
        st.info("No products added yet.")

# -------------------- ADD STOCK --------------------
elif page == "Add Stock":
    st.title("🏭 Add Stock")
    products = get_products()
    if products.empty:
        st.warning("Add products first")
        st.stop()

    # Convert to records for selectbox usage
    product_options = products.to_dict(orient="records")

    # Show only product name in dropdown (flavor_name)
    # Batch cost is computed automatically as quantity * product cost_price
    # and stored in stock_additions so Cost Used (production) updates when stock is increased.
    # Product and quantity selection are OUTSIDE the form so they update immediately
    sel = st.selectbox(
        "Select Product",
        options=product_options,
        format_func=lambda r: r["flavor_name"],
        key="add_stock_product_select"
    )

    # quantity input (outside form so it updates immediately)
    qty = st.number_input("Quantity", min_value=1, step=1, value=1, key="add_stock_qty")

    # compute batch cost automatically using product cost_price * qty
    prod_cost_price = float(sel.get("cost_price", 0.0) or 0.0)
    batch_cost = float(qty) * prod_cost_price

    # show computed batch cost as a metric for clarity (updates dynamically without caching issues)
    st.metric("Batch Cost (total for this batch)", f"₹{batch_cost:.2f}")

    # Form only contains date and submit button
    with st.form("stock"):
        d = st.date_input("Date", value=date.today(), key="add_stock_date")

        if st.form_submit_button("Add Stock"):
            pid = int(sel["id"])
            # Insert computed batch_cost into stock_additions and update product stock
            c.execute("INSERT INTO stock_additions(product_id,date,quantity,batch_cost) VALUES (?,?,?,?)",
                      (pid, d.isoformat(), int(qty), float(batch_cost)))
            c.execute("UPDATE products SET stock = stock + ? WHERE id=?", (int(qty), pid))
            conn.commit()
            # Show a simple confirmation; batch cost is already visible in the input above
            st.success("Stock added")
            run_rerun()

# -------------------- RECORD SALE --------------------
elif page == "Record Sale":
    st.title("💰 Record Sale")
    products = get_products()
    customers = get_customers()

    if products.empty:
        st.warning("Add products first")
        st.stop()

    # Product selection (outside form so details update immediately)
    product_records = products.to_dict(orient="records")
    product_options = [{"id": int(r["id"]), "label": r["flavor_name"], "data": r} for r in product_records]
    selected_product = st.selectbox(
        "Select Product",
        options=product_options,
        format_func=lambda x: x["label"],
        key="product_select"
    )
    sel = selected_product["data"]

    # Show product details immediately
    st.markdown("**Product Details**")
    pcol1, pcol2, pcol3 = st.columns(3)
    pcol1.text_input("Cost Price", value=f"₹{sel['cost_price']:.2f}", disabled=True)
    pcol2.text_input("Selling Price", value=f"₹{sel['selling_price']:.2f}", disabled=True)
    pcol3.text_input("Available Stock", value=str(int(sel["stock"])), disabled=True)

    # Customer selection (outside form so details update immediately)
    cust_options = [{"id": "add_new", "name": "Add new customer"}]
    cust_options += [{"id": int(r["id"]), "name": r["name"]} for _, r in customers.iterrows()]
    cust_sel = st.selectbox("Choose customer", options=cust_options, format_func=lambda x: x["name"], key="cust_select")

    if cust_sel["id"] == "add_new":
        new_cust_name = st.text_input("Customer Name")
        new_cust_phone = st.text_input("Phone Number")
        new_cust_shop = st.text_input("Shop Name")
        new_cust_area = st.text_input("Area")
        selected_customer_id = None
    else:
        selected_customer_id = int(cust_sel["id"])
        cust_row = customers[customers["id"] == selected_customer_id]
        if not cust_row.empty:
            cust_row = cust_row.iloc[0]
            c1, c2 = st.columns(2)
            name_val = c1.text_input("Customer Name", value=cust_row["name"])
            phone_val = c2.text_input("Phone Number", value=cust_row["phone"] if cust_row["phone"] else "")
            c3, c4 = st.columns(2)
            shop_val = c3.text_input("Shop Name", value=cust_row["shop_name"] if cust_row["shop_name"] else "")
            area_val = c4.text_input("Area", value=cust_row["area"] if cust_row["area"] else "")
        else:
            name_val = st.text_input("Customer Name", value="", disabled=True)
            phone_val = st.text_input("Phone Number", value="", disabled=True)
            shop_val = st.text_input("Shop Name", value="", disabled=True)
            area_val = st.text_input("Area", value="", disabled=True)

    # Sale form (only quantity/date/submit)
    with st.form("sale_form"):
        qty = st.number_input("Quantity Sold", min_value=1, step=1, value=1)
        d = st.date_input("Date", value=date.today())
        if st.form_submit_button("Record Sale"):
            if int(qty) > int(sel["stock"]):
                st.error("Not enough stock")
            else:
                # Handle customer
                if cust_sel["id"] == "add_new":
                    if not new_cust_name or not new_cust_name.strip():
                        st.error("Enter customer name")
                        st.stop()
                    c.execute("INSERT INTO customers(name, phone, shop_name, area) VALUES (?,?,?,?)",
                              (new_cust_name.strip(),
                               new_cust_phone.strip() if new_cust_phone else None,
                               new_cust_shop.strip() if new_cust_shop else None,
                               new_cust_area.strip() if new_cust_area else None))
                    conn.commit()
                    customer_id = c.lastrowid
                else:
                    if not name_val or not name_val.strip():
                        st.error("Customer name cannot be empty")
                        st.stop()
                    c.execute("UPDATE customers SET name=?, phone=?, shop_name=?, area=? WHERE id=?",
                              (name_val.strip(), phone_val.strip() if phone_val else None,
                               shop_val.strip() if shop_val else None, area_val.strip() if area_val else None,
                               selected_customer_id))
                    conn.commit()
                    customer_id = selected_customer_id

                # Record sale and update stock
                revenue = int(qty) * float(sel["selling_price"])
                c.execute("INSERT INTO sales(product_id,date,quantity,revenue,customer_id) VALUES (?,?,?,?,?)",
                          (int(sel["id"]), d.isoformat(), int(qty), float(revenue), int(customer_id)))
                c.execute("UPDATE products SET stock = stock - ? WHERE id=?", (int(qty), int(sel["id"])))
                conn.commit()
                st.success(f"Sale recorded ₹{revenue:.2f}")
                run_rerun()

# -------------------- COMPANY INVESTMENT --------------------
elif page == "Company Investment":
    st.title("🏦 Company Investment")
    with st.form("invest"):
        amt = st.number_input("Investment Amount", min_value=0.0, format="%.2f")
        note = st.text_input("Note")
        if st.form_submit_button("Add Investment"):
            c.execute("INSERT INTO investments(date,amount,note) VALUES (?,?,?)",
                      (date.today().isoformat(), float(amt), note.strip() if note else None))
            conn.commit()
            st.success("Investment added")
            run_rerun()
    investments = pd.read_sql("SELECT * FROM investments ORDER BY date DESC", conn)
    st.dataframe(investments)

# -------------------- REPORTS --------------------
elif page == "Reports & Graphs":

    st.title("📈 Business Reports")

    # ---------------- SALES DATA ----------------
    sales = pd.read_sql("""
        SELECT s.date, f.flavor_name, s.quantity, s.revenue, c.name customer
        FROM sales s
        JOIN products p ON s.product_id = p.id
        LEFT JOIN flavors f ON p.flavor_id = f.id
        LEFT JOIN customers c ON s.customer_id = c.id
    """, conn)

    stock = get_products()

    if sales.empty:
        st.info("No sales recorded yet.")
        st.stop()

    sales["date"] = pd.to_datetime(sales["date"])
    sales["month"] = sales["date"].dt.to_period("M").astype(str)

    # ---------------- MONTHLY SUMMARY ----------------
    st.subheader("📅 Monthly Revenue & Profit")

    cost = pd.read_sql("""
        SELECT date, batch_cost
        FROM stock_additions
    """, conn)

    cost["date"] = pd.to_datetime(cost["date"])
    cost["month"] = cost["date"].dt.to_period("M").astype(str)

    monthly_revenue = sales.groupby("month")["revenue"].sum()
    monthly_cost = cost.groupby("month")["batch_cost"].sum()

    monthly = pd.concat([monthly_revenue, monthly_cost], axis=1).fillna(0)
    monthly.columns = ["Revenue", "Cost"]
    monthly["Profit"] = monthly["Revenue"] - monthly["Cost"]

    st.dataframe(monthly)

    st.line_chart(monthly)

    # ---------------- TOP FLAVORS ----------------
    st.subheader("🥤 Top Selling Flavors")

    top_flavor = sales.groupby("flavor_name").agg({
        "quantity": "sum",
        "revenue": "sum"
    }).sort_values("revenue", ascending=False)

    st.dataframe(top_flavor)

    st.bar_chart(top_flavor["revenue"])

    # ---------------- BEST CUSTOMERS ----------------
    st.subheader("👥 Best Customers")

    top_customers = sales.groupby("customer").agg({
        "quantity": "sum",
        "revenue": "sum"
    }).sort_values("revenue", ascending=False)

    st.dataframe(top_customers)

    # ---------------- LOW STOCK ----------------
    st.subheader("⚠️ Low Stock Report")

    low = stock[stock["stock"] < 10]

    if not low.empty:
        st.dataframe(low[["flavor_name", "stock"]])
    else:
        st.success("Stock level is healthy ✅")

# -------------------- FINANCIAL SUMMARY --------------------
elif page == "Financial Summary":
    st.title("📑 Financial Summary")
    sales = pd.read_sql("SELECT * FROM sales", conn)
    products = get_products()

    revenue = sales["revenue"].sum() if not sales.empty else 0
    # Cost Used = total production cost incurred (sum of batch_cost from stock_additions)
    cost_used_row = pd.read_sql("""
        SELECT COALESCE(SUM(batch_cost), 0) AS cost_used
        FROM stock_additions
    """, conn)
    cost_used = float(cost_used_row["cost_used"].iloc[0]) if not cost_used_row.empty else 0.0
    profit = revenue - cost_used

    st.metric("Revenue", f"₹{revenue:,.2f}")
    st.metric("Cost Used (Production)", f"₹{cost_used:,.2f}")
    st.metric("Profit / Loss", f"₹{profit:,.2f}")

# -------------------- CUSTOMERS --------------------
elif page == "Customers":
    st.title("👥 Customer Management")
    customers = get_customers()
    with st.form("add_customer"):
        name = st.text_input("Name")
        phone = st.text_input("Phone")
        shop = st.text_input("Shop Name")
        area = st.text_input("Area")
        if st.form_submit_button("Add Customer"):
            if name and name.strip():
                c.execute("INSERT INTO customers(name, phone, shop_name, area) VALUES (?,?,?,?)",
                          (name.strip(), phone.strip() if phone else None, shop.strip() if shop else None, area.strip() if area else None))
                conn.commit()
                st.success("Customer added")
                run_rerun()
            else:
                st.error("Name is required")

    if not customers.empty:
        for _, row in customers.iterrows():
            col1,col2,col3,col4,col5,col6 = st.columns([3,2,2,2,2,1])
            col1.write(row["name"])
            col2.write(row["phone"])
            col3.write(row["shop_name"])
            col4.write(row["area"])
            if col5.button("✏️ Edit", key=f"cust_edit_{row['id']}"):
                st.session_state.edit_customer_id = int(row["id"])
            if col6.button("🗑", key=f"cust_del_{row['id']}"):
                c.execute("DELETE FROM customers WHERE id=?", (int(row["id"]),))
                conn.commit()
                st.success("Customer deleted")
                run_rerun()
        if "edit_customer_id" in st.session_state:
            cid = st.session_state.edit_customer_id
            cust = customers[customers["id"]==cid].iloc[0]
            with st.form("edit_customer"):
                new_name = st.text_input("Name", cust["name"])
                new_phone = st.text_input("Phone", cust["phone"])
                new_shop = st.text_input("Shop Name", cust["shop_name"])
                new_area = st.text_input("Area", cust["area"])
                if st.form_submit_button("Update Customer"):
                    c.execute("UPDATE customers SET name=?, phone=?, shop_name=?, area=? WHERE id=?",
                              (new_name.strip(), new_phone.strip() if new_phone else None,
                               new_shop.strip() if new_shop else None, new_area.strip() if new_area else None, cid))
                    conn.commit()
                    st.success("Customer updated")
                    del st.session_state.edit_customer_id
                    run_rerun()
    else:
        st.info("No customers added yet.")
