# app.py
import streamlit as st
import pandas as pd
import sqlite3
from datetime import date
import plotly.express as px
import os
import hashlib

# ---------------- CLOUD SAFE SESSION ----------------

if "user" not in st.session_state:
    st.session_state.user = None

if "page" not in st.session_state:
    st.session_state.page = "Dashboard"

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
                
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE,
    password_hash TEXT,
    role TEXT DEFAULT 'staff'
);

-- Activity Log
CREATE TABLE IF NOT EXISTS activity_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT,
    action TEXT,
    date TEXT
);
""")
conn.commit()

# -------------------- AUTO MIGRATION (SAFE) --------------------

def add_column_if_not_exists(table, column, col_type):

    cols = c.execute(f"PRAGMA table_info({table})").fetchall()
    col_names = [col[1] for col in cols]

    if column not in col_names:
        c.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
        conn.commit()


# Products
add_column_if_not_exists("products", "created_by", "TEXT")
add_column_if_not_exists("products", "updated_by", "TEXT")
add_column_if_not_exists("products", "created_at", "TEXT")
add_column_if_not_exists("products", "updated_at", "TEXT")

# Customers
add_column_if_not_exists("customers", "created_by", "TEXT")
add_column_if_not_exists("customers", "updated_by", "TEXT")
add_column_if_not_exists("customers", "created_at", "TEXT")
add_column_if_not_exists("customers", "updated_at", "TEXT")

# Stock
add_column_if_not_exists("stock_additions", "created_by", "TEXT")
add_column_if_not_exists("stock_additions", "created_at", "TEXT")

# Sales
add_column_if_not_exists("sales", "created_by", "TEXT")
add_column_if_not_exists("sales", "created_at", "TEXT")

# -------------------- CONFIG --------------------
st.set_page_config(page_title="Soda Business Manager", layout="wide")
# APP_PASSWORD = "soda123"

# -------------------- RERUN / REFRESH HELPERS --------------------
def run_rerun():
    """
    Trigger a full page rerun to refresh data immediately.
    """
    st.rerun()

# -------------------- HELPERS --------------------
def get_flavors():
    df = pd.read_sql("SELECT * FROM flavors ORDER BY flavor_name", conn)
    if "flavor_name" in df.columns:
        df["flavor_name"] = df["flavor_name"].fillna("Unknown flavor")
    return df

def get_products():
    df = pd.read_sql("""
        SELECT p.id, p.flavor_id, p.cost_price, p.selling_price, p.stock, f.flavor_name, p.created_by, p.created_at, p.updated_by, p.updated_at
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

# -------------------- SESSION PERSISTENCE --------------------

SESSION_FILE = "auth_session.txt"


def save_session(user, page="Dashboard"):
    with open(SESSION_FILE, "w") as f:
        f.write(f"{user['id']}|{user['username']}|{user['role']}|{page}")


def load_session():

    if not os.path.exists(SESSION_FILE):
        return None

    try:
        with open(SESSION_FILE) as f:
            data = f.read().strip()

        if not data:
            return None

        uid, uname, role, page = data.split("|")

        return {
            "id": int(uid),
            "username": uname,
            "role": role,
            "page": page
        }

    except:
        return None

# -------------------- AUTH HELPERS -----------------

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def create_user(username, password, role="staff"):
    try:
        c.execute("""
        INSERT INTO users(username,password_hash,role)
        VALUES(?,?,?)
        """, (username, hash_password(password), role))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False


def verify_user(username, password):
    hashed = hash_password(password)

    user = c.execute("""
        SELECT id, role FROM users
        WHERE username=? AND password_hash=?
    """, (username, hashed)).fetchone()

    return user

# -------------------- AUDIT HELPERS --------------------

def current_user():
    return st.session_state.user["username"]


def log_activity(action):

    user = st.session_state.get("user")

    if not user:
        return

    c.execute("""
        INSERT INTO activity_logs(username,action,date)
        VALUES (?,?,?)
    """, (
        user["username"],
        action,
        date.today().isoformat()
    ))

    conn.commit()

# -------------------- AUTH (MULTI USER) --------------------

if "user" not in st.session_state:

    saved = load_session()

    if saved:
        st.session_state.user = saved
    else:
        st.session_state.user = None

# Create first admin (only if no users exist)
user_count = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]

if user_count == 0:
    create_user("admin", "admin123", "admin")


if st.session_state.user is None:

    st.title("🔐 Login")

    tab1, tab2 = st.tabs(["Login", "Register"])

    # ---------- LOGIN ----------
    with tab1:

        username = st.text_input("Username", key="login_user")
        password = st.text_input("Password", type="password", key="login_pass")

        if st.button("Login"):

            user = verify_user(username, password)

            if user:
                st.session_state.user = {
                    "id": user[0],
                    "username": username,
                    "role": user[1]
                }
                save_session(st.session_state.user, "Dashboard")
                st.success("Login successful")
                st.rerun()
            else:
                st.error("Invalid credentials")

    # ---------- REGISTER ----------
    with tab2:

        new_user = st.text_input("New Username")
        new_pass = st.text_input("New Password", type="password")

        if st.button("Register"):

            if len(new_pass) < 4:
                st.error("Password too short")
            else:
                ok = create_user(new_user, new_pass)

                if ok:
                    st.success("Account created. Login now.")
                else:
                    st.error("Username already exists")

    st.stop()


# ---------- LOGOUT ----------
st.sidebar.write(f"👤 {st.session_state.user['username']}")

if st.sidebar.button("Logout"):

    clear_session()
    st.session_state.user = None
    st.rerun()

# -------------------- SIDEBAR --------------------
st.sidebar.title("🥤 Soda Manager")
# bind radio to session_state so we can change it programmatically
pages = [
    "Dashboard",
    "Flavors",
    "Products",
    "Add Stock",
    "Record Sale",
    "Company Investment",
    "Reports & Graphs",
    "Financial Summary",
    "Customers",
    "Admin Activity"
]

default_page = st.session_state.get("page", "Dashboard")

if default_page not in pages:
    default_page = "Dashboard"

page = st.sidebar.radio(
    "Navigation",
    pages,
    index=pages.index(default_page),
    key="page"
)

# Save current page
save_session(st.session_state.user, page)

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
        st.dataframe(
    products[[
        "flavor_name",
        "cost_price",
        "selling_price",
        "stock",
        "created_by",
        "created_at",
        "updated_by",
        "updated_at"
    ]],
    use_container_width=True
)
        
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
            c.execute("INSERT INTO products(flavor_id, cost_price, selling_price, stock, created_by, created_at) values (?,?,?,?,?,?)",
                      (flavor_id, float(cost), float(price), int(stock), current_user(), date.today().isoformat()))
            conn.commit()
            log_activity(f"Added product for flavor {flavor_choice['flavor_name']}")
            st.success("Product added")
            run_rerun()

    if not products.empty:
        for _, row in products.iterrows():
            col1,col2,col3,col4,col5,col6,col7 = st.columns([3,2,2,2,2,2,1])
            col1.write(row["flavor_name"])
            col2.write(f"₹{row['cost_price']:.2f}")
            col3.write(f"₹{row['selling_price']:.2f}")
            col4.write(f"Stock: {int(row['stock'])}")
            col5.write(f"By: {row['created_by']}")
            col6.write(f"Upd: {row['updated_by']}")
            col7.write(row['updated_at'])
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
                    c.execute("UPDATE products SET flavor_id=?, cost_price=?, selling_price=?, stock=?, updated_by=?, updated_at=? WHERE id=?",
                              (flavor_id, float(cost), float(price), int(stock), current_user(), date.today().isoformat(), pid))
                    conn.commit()
                    log_activity(f"Updated product {flavor_choice['flavor_name']}")
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
            c.execute("INSERT INTO stock_additions(product_id,date,quantity,batch_cost, created_by,created_at) VALUES (?,?,?,?,?,?)",
                      (pid, d.isoformat(), int(qty), float(batch_cost), current_user(), date.today().isoformat()))
            c.execute("UPDATE products SET stock = stock + ? WHERE id=?", (int(qty), pid))
            conn.commit()
            log_activity(f"Added {qty} stock to {sel['flavor_name']}")
            # Show a simple confirmation; batch cost is already visible in the input above
            st.success("Stock added")
            run_rerun()
            st.markdown("## 📦 Stock Addition History")

        stock_df = pd.read_sql("""
            SELECT
                s.id,
                f.flavor_name,
                s.date,
                s.quantity,
                s.batch_cost,
                s.created_by,
                s.created_at
            FROM stock_additions s
            LEFT JOIN products p ON s.product_id = p.id
            LEFT JOIN flavors f ON p.flavor_id = f.id
            ORDER BY s.id DESC
        """, conn)

        if stock_df.empty:
            st.info("No stock added yet.")
        else:
            st.dataframe(stock_df, use_container_width=True)

# -------------------- RECORD SALE --------------------
elif page == "Record Sale":

    st.title("🧾 Record Sale")

    products = get_products()
    customers = get_customers()

    if products.empty:
        st.warning("No products available.")
        st.stop()

    # ------------------ Product Selection ------------------

    prod_options = products.to_dict("records")

    sel = st.selectbox(
        "Select Product",
        prod_options,
        format_func=lambda x: f"{x['flavor_name']} (Stock: {x['stock']})"
    )

    if sel["stock"] <= 0:
        st.error("Selected product is out of stock.")
        st.stop()


    # ------------------ Customer Selection ------------------

    cust_options = [{"id": "add_new", "name": "➕ Add New Customer"}]

    for _, r in customers.iterrows():
        cust_options.append({
            "id": r["id"],
            "name": r["name"]
        })


    cust_sel = st.selectbox(
        "Select Customer",
        cust_options,
        format_func=lambda x: x["name"]
    )


    # ------------------ Customer Form ------------------

    # Initialize variables
    new_cust_name = ""
    new_cust_phone = ""
    new_cust_shop = ""
    new_cust_area = ""

    name_val = ""
    phone_val = ""
    shop_val = ""
    area_val = ""
    selected_customer_id = None


    if cust_sel["id"] == "add_new":

        st.subheader("➕ New Customer")

        new_cust_name = st.text_input("Customer Name")
        new_cust_phone = st.text_input("Phone")
        new_cust_shop = st.text_input("Shop Name")
        new_cust_area = st.text_input("Area")

    else:

        selected_customer_id = int(cust_sel["id"])

        row = customers[customers["id"] == selected_customer_id].iloc[0]

        name_val = st.text_input("Customer Name", row["name"])
        phone_val = st.text_input("Phone", row["phone"])
        shop_val = st.text_input("Shop Name", row["shop_name"])
        area_val = st.text_input("Area", row["area"])


    # ------------------ Sale Form ------------------

    with st.form("sale_form"):

        qty = st.number_input(
            "Quantity Sold",
            min_value=1,
            max_value=int(sel["stock"]),
            step=1,
            value=1
        )

        d = st.date_input("Sale Date", value=date.today())

        submit_sale = st.form_submit_button("Record Sale")


    # ------------------ Process Sale ------------------

    if submit_sale:

        # Validate stock
        if int(qty) > int(sel["stock"]):
            st.error("Not enough stock.")
            st.stop()


        # Handle customer
        if cust_sel["id"] == "add_new":

            if not new_cust_name.strip():
                st.error("Customer name is required.")
                st.stop()

            # Insert new customer
            c.execute("""
                INSERT INTO customers(
                    name, phone, shop_name, area,
                    created_by, created_at
                )
                VALUES (?,?,?,?,?,?)
            """, (
                new_cust_name.strip(),
                new_cust_phone.strip() if new_cust_phone else None,
                new_cust_shop.strip() if new_cust_shop else None,
                new_cust_area.strip() if new_cust_area else None,
                current_user(),
                date.today().isoformat()
            ))

            conn.commit()

            customer_id = c.lastrowid


        else:

            # Update existing customer
            c.execute("""
                UPDATE customers
                SET name=?, phone=?, shop_name=?, area=?,
                    updated_by=?, updated_at=?
                WHERE id=?
            """, (
                name_val.strip(),
                phone_val.strip() if phone_val else None,
                shop_val.strip() if shop_val else None,
                area_val.strip() if area_val else None,
                current_user(),
                date.today().isoformat(),
                selected_customer_id
            ))

            conn.commit()

            customer_id = selected_customer_id


        # Calculate revenue
        revenue = int(qty) * float(sel["selling_price"])


        # Insert sale
        c.execute("""
            INSERT INTO sales(
                product_id,
                date,
                quantity,
                revenue,
                customer_id,
                created_by,
                created_at
            )
            VALUES (?,?,?,?,?,?,?)
        """, (
            int(sel["id"]),
            d.isoformat(),
            int(qty),
            float(revenue),
            int(customer_id),
            current_user(),
            date.today().isoformat()
        ))


        # Update stock
        c.execute("""
            UPDATE products
            SET stock = stock - ?
            WHERE id=?
        """, (
            int(qty),
            int(sel["id"])
        ))


        conn.commit()


        # Log activity
        log_activity(f"Sold {qty} of {sel['flavor_name']}")


        st.success("✅ Sale recorded successfully.")

        st.rerun()


    # ------------------ Sales History ------------------

    st.markdown("## 📋 Sales History")

    sales_df = pd.read_sql("""
        SELECT 
            s.id,
            f.flavor_name,
            s.date,
            s.quantity,
            s.revenue,
            c.name AS customer,
            s.created_by,
            s.created_at
        FROM sales s
        LEFT JOIN products p ON s.product_id = p.id
        LEFT JOIN flavors f ON p.flavor_id = f.id
        LEFT JOIN customers c ON s.customer_id = c.id
        ORDER BY s.id DESC
    """, conn)


    if sales_df.empty:
        st.info("No sales recorded yet.")
    else:
        st.dataframe(sales_df, use_container_width=True)

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
                c.execute("INSERT INTO customers(name, phone, shop_name, area, created_by, created_at) VALUES (?,?,?,?,?,?)",
                          (name.strip(), phone.strip() if phone else None, shop.strip() if shop else None, area.strip() if area else None, current_user(), date.today().isoformat()))
                conn.commit()
                log_activity(f"Added customer {name}")
                st.success("Customer added")
                run_rerun()
            else:
                st.error("Name is required")

    if not customers.empty:
        for _, row in customers.iterrows():
            col1,col2,col3,col4,col5,col6,col7,col8 = st.columns([2,2,2,2,2,2,2,1])
            col1.write(row["name"])
            col2.write(row["phone"])
            col3.write(row["shop_name"])
            col4.write(row["area"])
            col5.write(f"By: {row['created_by']}")
            col6.write(f"Upd: {row['updated_by']}")
            col7.write(row['updated_at'])
            if col8.button("✏️ Edit", key=f"cust_edit_{row['id']}"):
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
                    c.execute("UPDATE customers SET name=?, phone=?, shop_name=?, area=?, updated_by=?, updated_at=? WHERE id=?",
                              (new_name.strip(), new_phone.strip() if new_phone else None,
                               new_shop.strip() if new_shop else None, new_area.strip() if new_area else None, current_user(), date.today().isoformat(), cid))
                    conn.commit()
                    log_activity(f"Updated customer {new_name}")
                    st.success("Customer updated")
                    del st.session_state.edit_customer_id
                    run_rerun()
    else:
        st.info("No customers added yet.")

# -------------------- ADMIN ACTIVITY --------------------

elif page == "Admin Activity":

    if st.session_state.user["role"] != "admin":
        st.error("Admins only 🚫")
        st.stop()

    st.title("🛡️ System Activity Log")

    logs = pd.read_sql("""
    SELECT 
        id,
        username,
        action,
        date
    FROM activity_logs
    ORDER BY id DESC
""", conn)

    if logs.empty:
        st.info("No activity yet")
    else:
        st.dataframe(logs, use_container_width=True)