import os
import uuid

from functools import wraps

from flask import (
    Flask,
    render_template,
    render_template_string,
    request,
    redirect,
    url_for,
    session,
    flash,
    send_from_directory
)

from werkzeug.utils import secure_filename

from database import get_db_connection


# =====================================================
# APP CONFIGURATION
# =====================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static")
)

app.secret_key = "neon_clothing_secret_key"

# Maximum uploaded file size = 5 MB
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024


# =====================================================
# COMMON SETTINGS
# =====================================================

VALID_SIZES = [
    "M",
    "L",
    "XL",
    "XXL",
    "30",
    "32",
    "36",
    "38"
]

FREE_DELIVERY_LIMIT = 2000
DELIVERY_CHARGE = 99

ALLOWED_IMAGE_EXTENSIONS = {
    "jpg",
    "jpeg",
    "png",
    "webp"
}

PRODUCT_IMAGE_FOLDER = os.path.join(
    BASE_DIR,
    "static",
    "images",
    "products"
)


# =====================================================
# REVIEW / RATING SETTINGS
# =====================================================

REVIEW_IMAGE_FOLDER = os.path.join(
    BASE_DIR,
    "static",
    "images",
    "reviews"
)

ALLOWED_REVIEW_IMAGE_EXTENSIONS = {
    "jpg",
    "jpeg",
    "png",
    "webp"
}

MAX_REVIEW_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MB


# =====================================================
# ADMIN LOGIN DETAILS
# =====================================================

ADMIN_EMAIL = "admin@neonclothing.com"
ADMIN_PASSWORD = "admin123"


# =====================================================
# PRODUCT CATEGORY / SUBCATEGORY DATA
# =====================================================

PRODUCT_TYPES = {
    "Shirts": [
        "Formal Shirt",
        "Casual Shirt",
        "Checked Shirt",
        "Half Sleeve Shirt",
        "Striped Shirt",
        "Linen Shirt",
        "Oversized Shirt"
    ],

    "Jeans": [
        "Regular Jeans",
        "Mom Fit Jeans",
        "Baggy Jeans"
    ],

    "T-Shirts": [
        "Round Neck",
        "Printed Neck",
        "Oversized T-Shirt",
        "Graphic T-Shirt"
    ],

    "Hoodies": [
        "Oversized Hoodie",
        "Acid Wash Hoodie",
        "Zipper Hoodie"
    ],

    "Track Pants": [
        "Straight Fit Pants"
    ],

    "Formal Pants": [
        "Gurkha Pants",
        "Slim Fit",
        "Bootcut"
    ]
}


MAIN_CATEGORIES = [
    "Jeans",
    "T-Shirts",
    "Hoodies",
    "Track Pants",
    "Formal Pants",
    "Shirts"
]


# =====================================================
# ADMIN AUTHENTICATION DECORATOR
# =====================================================

def admin_required(view_function):

    @wraps(view_function)
    def wrapper(*args, **kwargs):

        if not session.get("admin_logged_in"):

            flash(
                "Please login to access the Admin Panel.",
                "error"
            )

            return redirect(
                url_for("admin_login")
            )

        return view_function(*args, **kwargs)

    return wrapper


# =====================================================
# DATABASE COLUMN CHECK
# =====================================================

def ensure_product_subcategory_column():
    """
    Make sure products.subcategory exists.

    This prevents errors when the existing database was created
    before the subcategory feature was added.
    """

    connection = get_db_connection()
    cursor = connection.cursor()

    try:

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'products'
              AND COLUMN_NAME = 'subcategory'
            """
        )

        result = cursor.fetchone()

        column_exists = result[0] if result else 0

        if not column_exists:

            cursor.execute(
                """
                ALTER TABLE products
                ADD COLUMN subcategory VARCHAR(100) NULL
                AFTER category_id
                """
            )

            connection.commit()

            print(
                "Created products.subcategory column successfully."
            )

    except Exception:

        connection.rollback()

        raise

    finally:

        cursor.close()
        connection.close()


# =====================================================
# IMAGE HELPERS
# =====================================================

def is_allowed_image(filename):
    """
    Check whether uploaded filename has an allowed extension.
    """

    if not filename or "." not in filename:
        return False

    extension = filename.rsplit(".", 1)[1].lower()

    return extension in ALLOWED_IMAGE_EXTENSIONS


def save_product_image(image_file):
    """
    Save uploaded product image into:

    static/images/products/

    Returns the database path:
    images/products/filename.jpg
    """

    if not image_file:
        return None, None

    original_filename = image_file.filename

    if not original_filename:
        return None, None

    if not is_allowed_image(original_filename):
        raise ValueError(
            "Only JPG, JPEG, PNG and WEBP images are allowed."
        )

    os.makedirs(
        PRODUCT_IMAGE_FOLDER,
        exist_ok=True
    )

    safe_filename = secure_filename(
        original_filename
    )

    if not safe_filename:
        raise ValueError(
            "Invalid image filename."
        )

    extension = safe_filename.rsplit(
        ".",
        1
    )[1].lower()

    unique_filename = (
        f"{uuid.uuid4().hex}.{extension}"
    )

    filesystem_path = os.path.join(
        PRODUCT_IMAGE_FOLDER,
        unique_filename
    )

    image_file.save(
        filesystem_path
    )

    database_path = (
        f"images/products/{unique_filename}"
    )

    return database_path, filesystem_path


def delete_local_product_image(image_path):
    """
    Delete only locally uploaded product images.

    External URLs are not touched.
    """

    if not image_path:
        return

    normalized_path = image_path.replace("\\", "/")

    prefix = "images/products/"

    if not normalized_path.startswith(prefix):
        return

    filename = normalized_path[
        len(prefix):
    ]

    if not filename:
        return

    full_path = os.path.join(
        PRODUCT_IMAGE_FOLDER,
        os.path.basename(filename)
    )

    try:

        if os.path.isfile(full_path):
            os.remove(full_path)

    except OSError:

        pass


# =====================================================
# PRODUCT IMAGE GALLERY DATABASE HELPERS
# =====================================================

def ensure_product_images_table():
    """
    Make sure the product_images table exists.

    One product can have any number of gallery images.
    """

    connection = get_db_connection()
    cursor = connection.cursor()

    try:

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS product_images (
                id INT AUTO_INCREMENT PRIMARY KEY,
                product_id INT NOT NULL,
                image_path TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT fk_product_images_product
                    FOREIGN KEY (product_id)
                    REFERENCES products(id)
                    ON DELETE CASCADE
                    ON UPDATE CASCADE
            )
            """
        )

        connection.commit()

    except Exception:

        connection.rollback()
        raise

    finally:

        cursor.close()
        connection.close()


def get_product_images(product_id):
    """Return all gallery images for one product."""

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:

        cursor.execute(
            """
            SELECT
                id,
                product_id,
                image_path,
                created_at
            FROM product_images
            WHERE product_id = %s
            ORDER BY id ASC
            """,
            (product_id,)
        )

        return cursor.fetchall()

    finally:

        cursor.close()
        connection.close()

# ============================================================
# REVIEWS & RATINGS TABLE
# ============================================================

def ensure_reviews_table():
    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reviews (
                id INT AUTO_INCREMENT PRIMARY KEY,
                product_id INT NOT NULL,
                user_id INT NOT NULL,
                rating TINYINT NOT NULL,
                review_text TEXT NOT NULL,
                image_path VARCHAR(500) NULL,
                is_verified TINYINT(1) NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                CONSTRAINT fk_reviews_product
                    FOREIGN KEY (product_id)
                    REFERENCES products(id)
                    ON DELETE CASCADE
                    ON UPDATE CASCADE,

                CONSTRAINT fk_reviews_user
                    FOREIGN KEY (user_id)
                    REFERENCES users(id)
                    ON DELETE CASCADE
                    ON UPDATE CASCADE,

                UNIQUE KEY unique_user_product_review
                    (user_id, product_id)
            )
        """)

        connection.commit()

    finally:
        cursor.close()
        connection.close()

# ============================================================
# REVIEWS TABLE
# ============================================================

def ensure_reviews_table():

    connection = get_db_connection()
    cursor = connection.cursor()

    try:

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reviews (

                id INT AUTO_INCREMENT PRIMARY KEY,

                product_id INT NOT NULL,

                user_id INT NOT NULL,

                rating TINYINT NOT NULL,

                review_text TEXT NOT NULL,

                image_path VARCHAR(500) NULL,

                is_verified TINYINT(1) NOT NULL DEFAULT 0,

                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                CONSTRAINT fk_reviews_product
                    FOREIGN KEY (product_id)
                    REFERENCES products(id)
                    ON DELETE CASCADE
                    ON UPDATE CASCADE,

                CONSTRAINT fk_reviews_user
                    FOREIGN KEY (user_id)
                    REFERENCES users(id)
                    ON DELETE CASCADE
                    ON UPDATE CASCADE,

                UNIQUE KEY unique_user_product_review
                    (user_id, product_id)

            )
        """)

        connection.commit()

    finally:

        cursor.close()
        connection.close()

# ============================================================
# REVIEW HELPERS
# ============================================================

def user_purchased_product(user_id, product_id):

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:

        cursor.execute("""
            SELECT oi.id
            FROM order_items oi

            INNER JOIN orders o
                ON o.id = oi.order_id

            WHERE o.user_id = %s
              AND oi.product_id = %s
              AND o.status = 'Delivered'

            LIMIT 1
        """, (user_id, product_id))

        return cursor.fetchone() is not None

    finally:

        cursor.close()
        connection.close()


def get_product_reviews(product_id):

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:

        cursor.execute("""
            SELECT
                r.id,
                r.rating,
                r.review_text,
                r.image_path,
                r.is_verified,
                r.created_at,
                u.name

            FROM reviews r

            INNER JOIN users u
                ON u.id = r.user_id

            WHERE r.product_id = %s

            ORDER BY
                r.created_at DESC,
                r.id DESC
        """, (product_id,))

        return cursor.fetchall()

    finally:

        cursor.close()
        connection.close()


def get_product_rating_summary(product_id):

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:

        cursor.execute("""
            SELECT
                COUNT(*) AS review_count,
                COALESCE(AVG(rating), 0) AS average_rating

            FROM reviews

            WHERE product_id = %s
        """, (product_id,))

        summary = cursor.fetchone()

        rating_breakdown = {}

        for star in range(5, 0, -1):

            cursor.execute("""
                SELECT COUNT(*) AS total

                FROM reviews

                WHERE product_id = %s
                  AND rating = %s
            """, (product_id, star))

            row = cursor.fetchone()

            rating_breakdown[star] = row["total"]

        return summary, rating_breakdown

    finally:

        cursor.close()
        connection.close()


def has_user_reviewed_product(user_id, product_id):

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT id
            FROM reviews
            WHERE user_id = %s
              AND product_id = %s
            LIMIT 1
        """, (user_id, product_id))

        return cursor.fetchone() is not None

    finally:
        cursor.close()
        connection.close()


# =====================================================
# YOUR EXISTING ROUTES
# =====================================================

@app.route("/")
def home():
    return render_template("index.html")




# ============================================================
# REVIEW IMAGE UPLOAD
# ============================================================

def save_review_image(image_file):

    if not image_file or not image_file.filename:
        return None

    original_filename = secure_filename(
        image_file.filename
    )

    if not original_filename:
        raise ValueError("Invalid image file.")

    extension = os.path.splitext(
        original_filename
    )[1].lower().replace(".", "")

    if extension not in ALLOWED_REVIEW_IMAGE_EXTENSIONS:
        raise ValueError(
            "Only JPG, JPEG, PNG and WEBP images are allowed."
        )

    os.makedirs(
        REVIEW_IMAGE_FOLDER,
        exist_ok=True
    )

    filename = (
        uuid.uuid4().hex
        + "."
        + extension
    )

    file_path = os.path.join(
        REVIEW_IMAGE_FOLDER,
        filename
    )

    image_file.save(file_path)

    # Check actual file size
    if os.path.getsize(file_path) > MAX_REVIEW_IMAGE_SIZE:

        os.remove(file_path)

        raise ValueError(
            "Review photo must be smaller than 5 MB."
        )

    # Path stored in database
    return os.path.join(
        "images",
        "reviews",
        filename
    ).replace("\\", "/")

# =====================================================
# GET PRODUCTS
# =====================================================

def get_products_from_db(
    category="All",
    subcategory="All"
):
    """
    Get products from MySQL.

    Supports:
    - category filtering
    - subcategory filtering
    """

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:

        query = """
            SELECT
                p.id,
                p.name,
                c.name AS category,
                p.category_id,
                p.subcategory,
                p.price,
                p.discount,
                p.stock,
                p.image,
                p.description,
                p.created_at
            FROM products p
            INNER JOIN categories c
                ON p.category_id = c.id
        """

        conditions = []
        params = []

        if category and category != "All":

            conditions.append(
                "LOWER(c.name) = LOWER(%s)"
            )

            params.append(category)

        if subcategory and subcategory != "All":

            conditions.append(
                "LOWER(COALESCE(p.subcategory, '')) = LOWER(%s)"
            )

            params.append(subcategory)

        if conditions:

            query += " WHERE "
            query += " AND ".join(conditions)

        query += """
            ORDER BY p.id ASC
        """

        cursor.execute(
            query,
            tuple(params)
        )

        return cursor.fetchall()

    finally:

        cursor.close()
        connection.close()


# =====================================================
# GET SINGLE PRODUCT
# =====================================================

def get_product_from_db(product_id):
    """
    Get one product from MySQL.
    """

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:

        cursor.execute(
            """
            SELECT
                p.id,
                p.name,
                c.name AS category,
                p.category_id,
                p.subcategory,
                p.price,
                p.discount,
                p.stock,
                p.image,
                p.description,
                p.created_at
            FROM products p
            INNER JOIN categories c
                ON p.category_id = c.id
            WHERE p.id = %s
            """,
            (product_id,)
        )

        return cursor.fetchone()

    finally:

        cursor.close()
        connection.close()


# =====================================================
# GET / CREATE CATEGORY
# =====================================================

def get_category_id(
    category_name,
    cursor
):
    """
    Find category by name.

    Create category when it does not exist.
    """

    category_name = (
        category_name or ""
    ).strip()

    cursor.execute(
        """
        SELECT id
        FROM categories
        WHERE LOWER(name) = LOWER(%s)
        LIMIT 1
        """,
        (category_name,)
    )

    row = cursor.fetchone()

    if row:

        if isinstance(row, dict):
            return row["id"]

        return row[0]

    cursor.execute(
        """
        INSERT INTO categories (name)
        VALUES (%s)
        """,
        (category_name,)
    )

    return cursor.lastrowid


# =====================================================
# GET ALL CATEGORIES
# =====================================================

def get_all_categories():

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:

        cursor.execute(
            """
            SELECT
                c.id,
                c.name,
                COUNT(p.id) AS count
            FROM categories c
            LEFT JOIN products p
                ON p.category_id = c.id
            GROUP BY
                c.id,
                c.name
            ORDER BY
                c.id ASC
            """
        )

        return cursor.fetchall()

    finally:

        cursor.close()
        connection.close()


# =====================================================
# CALCULATE CART
# =====================================================

def calculate_cart():
    """
    Build complete cart information from session + MySQL.
    """

    cart = session.get(
        "cart",
        []
    )

    cart_items = []

    original_subtotal = 0
    discount_total = 0
    subtotal = 0

    cleaned_cart = []

    for item in cart:

        try:

            product_id = int(
                item.get("product_id")
            )

        except (TypeError, ValueError):

            continue

        product = get_product_from_db(
            product_id
        )

        if not product:
            continue

        size = str(
            item.get("size", "")
        ).strip().upper()

        try:

            quantity = int(
                item.get("quantity", 1)
            )

        except (TypeError, ValueError):

            quantity = 1

        if size not in VALID_SIZES:
            size = "M"

        if quantity < 1:
            quantity = 1

        stock = int(
            product.get("stock") or 0
        )

        if stock <= 0:
            continue

        if quantity > stock:
            quantity = stock

        cleaned_cart.append(
            {
                "product_id": product["id"],
                "size": size,
                "quantity": quantity
            }
        )

        original_price = float(
            product["price"]
        )

        discount_percent = float(
            product.get("discount") or 0
        )

        discount_amount = (
            original_price
            * discount_percent
            / 100
        )

        final_price = (
            original_price
            - discount_amount
        )

        original_item_total = (
            original_price
            * quantity
        )

        discount_item_total = (
            discount_amount
            * quantity
        )

        item_total = (
            final_price
            * quantity
        )

        original_subtotal += (
            original_item_total
        )

        discount_total += (
            discount_item_total
        )

        subtotal += item_total

        cart_items.append(
            {
                "index": len(cleaned_cart) - 1,
                "product": product,
                "size": size,
                "quantity": quantity,
                "original_price": original_price,
                "discount_percent": discount_percent,
                "discount_amount": discount_amount,
                "final_price": final_price,
                "total": item_total
            }
        )

    if cleaned_cart != cart:

        session["cart"] = cleaned_cart
        session.modified = True

    if subtotal >= FREE_DELIVERY_LIMIT:

        delivery_charge = 0
        delivery_text = "FREE"

    else:

        delivery_charge = DELIVERY_CHARGE
        delivery_text = "₹99"

    grand_total = (
        subtotal
        + delivery_charge
    )

    return {
        "cart_items": cart_items,
        "original_subtotal": original_subtotal,
        "discount_total": discount_total,
        "subtotal": subtotal,
        "delivery_charge": delivery_charge,
        "delivery_text": delivery_text,
        "grand_total": grand_total,
        "free_delivery_limit": FREE_DELIVERY_LIMIT
    }


# =====================================================
# SEED DATABASE
# =====================================================

def seed_database():
    """
    Create basic categories/sample products only when
    products table is empty.
    """

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:

        # Make sure subcategory column exists.
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'products'
              AND COLUMN_NAME = 'subcategory'
            """
        )

        column_check = cursor.fetchone()

        if column_check and column_check[
            list(column_check.keys())[0]
        ] == 0:

            cursor.execute(
                """
                ALTER TABLE products
                ADD COLUMN subcategory VARCHAR(100) NULL
                AFTER category_id
                """
            )

            connection.commit()

        # Check product count
        cursor.execute(
            """
            SELECT COUNT(*) AS total
            FROM products
            """
        )

        product_count = cursor.fetchone()["total"]

        if product_count > 0:
            return

        # Main categories
        for category in MAIN_CATEGORIES:

            cursor.execute(
                """
                INSERT IGNORE INTO categories (name)
                VALUES (%s)
                """,
                (category,)
            )

        sample_products = [

            {
                "name": "Oversized Black T-Shirt",
                "category": "T-Shirts",
                "subcategory": "Oversized T-Shirt",
                "price": 799,
                "discount": 10,
                "stock": 20,
                "image": (
                    "https://placehold.co/600x750/"
                    "111111/dfff00?text=Black+T-Shirt"
                ),
                "description": (
                    "Premium oversized black T-shirt "
                    "with a modern streetwear fit."
                )
            },

            {
                "name": "Classic White T-Shirt",
                "category": "T-Shirts",
                "subcategory": "Round Neck",
                "price": 699,
                "discount": 15,
                "stock": 25,
                "image": (
                    "https://placehold.co/600x750/"
                    "f5f5f5/111111?text=White+T-Shirt"
                ),
                "description": (
                    "Clean and comfortable white T-shirt "
                    "for everyday wear."
                )
            },

            {
                "name": "Premium Casual Shirt",
                "category": "Shirts",
                "subcategory": "Casual Shirt",
                "price": 1199,
                "discount": 20,
                "stock": 15,
                "image": (
                    "https://placehold.co/600x750/"
                    "222222/dfff00?text=Casual+Shirt"
                ),
                "description": (
                    "Stylish casual shirt designed for "
                    "a smart modern look."
                )
            },

            {
                "name": "Checked Shirt",
                "category": "Shirts",
                "subcategory": "Checked Shirt",
                "price": 1299,
                "discount": 0,
                "stock": 12,
                "image": (
                    "https://placehold.co/600x750/"
                    "333333/dfff00?text=Checked+Shirt"
                ),
                "description": (
                    "Trendy checked shirt for casual "
                    "and everyday styling."
                )
            },

            {
                "name": "Regular Blue Jeans",
                "category": "Jeans",
                "subcategory": "Regular Jeans",
                "price": 1499,
                "discount": 0,
                "stock": 18,
                "image": (
                    "https://placehold.co/600x750/"
                    "172554/dfff00?text=Blue+Jeans"
                ),
                "description": (
                    "Comfortable regular-fit jeans with "
                    "a stylish modern finish."
                )
            },

            {
                "name": "Baggy Jeans",
                "category": "Jeans",
                "subcategory": "Baggy Jeans",
                "price": 1599,
                "discount": 13,
                "stock": 10,
                "image": (
                    "https://placehold.co/600x750/"
                    "111111/dfff00?text=Baggy+Jeans"
                ),
                "description": (
                    "Relaxed baggy jeans perfect for "
                    "modern streetwear outfits."
                )
            },

            {
                "name": "Oversized Hoodie",
                "category": "Hoodies",
                "subcategory": "Oversized Hoodie",
                "price": 1499,
                "discount": 10,
                "stock": 15,
                "image": (
                    "https://placehold.co/600x750/"
                    "18181b/dfff00?text=Hoodie"
                ),
                "description": (
                    "Warm oversized hoodie with a trendy "
                    "streetwear silhouette."
                )
            },

            {
                "name": "Track Pants",
                "category": "Track Pants",
                "subcategory": "Straight Fit Pants",
                "price": 999,
                "discount": 20,
                "stock": 16,
                "image": (
                    "https://placehold.co/600x750/"
                    "1f2937/dfff00?text=Track+Pants"
                ),
                "description": (
                    "Comfortable straight-fit track pants "
                    "for casual and active wear."
                )
            },

            {
                "name": "Gurkha Formal Pants",
                "category": "Formal Pants",
                "subcategory": "Gurkha Pants",
                "price": 1399,
                "discount": 10,
                "stock": 10,
                "image": (
                    "https://placehold.co/600x750/"
                    "262626/dfff00?text=Formal+Pants"
                ),
                "description": (
                    "Classic Gurkha-style formal pants "
                    "for a clean premium look."
                )
            }

        ]

        for product in sample_products:

            category_id = get_category_id(
                product["category"],
                cursor
            )

            cursor.execute(
                """
                INSERT INTO products
                (
                    name,
                    category_id,
                    subcategory,
                    price,
                    discount,
                    stock,
                    image,
                    description
                )
                VALUES
                (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                )
                """,
                (
                    product["name"],
                    category_id,
                    product["subcategory"],
                    product["price"],
                    product["discount"],
                    product["stock"],
                    product["image"],
                    product["description"]
                )
            )

        connection.commit()

        print(
            "Sample Neon Clothing products inserted."
        )

    finally:

        cursor.close()
        connection.close()




# =====================================================
# PRODUCTS
# =====================================================

@app.route("/products")
def products():

    category = request.args.get(
        "category",
        "All"
    ).strip()

    subcategory = request.args.get(
        "subcategory",
        "All"
    ).strip()

    filtered_products = get_products_from_db(
        category,
        subcategory
    )

    return render_template(
        "products.html",
        products=filtered_products,
        selected_category=category,
        selected_subcategory=subcategory,
        product_types=PRODUCT_TYPES,
        categories=MAIN_CATEGORIES
    )


# =====================================================
# PRODUCT DETAILS
# =====================================================
@app.route("/product/<int:product_id>")
def product_details(product_id):

    product = get_product_from_db(product_id)

    if product is None:
        return ("Product not found", 404)

    # ========================================================
    # PRODUCT GALLERY
    # ========================================================

    gallery_rows = get_product_images(product_id)

    product_images = [
        row["image_path"]
        for row in gallery_rows
        if row.get("image_path")
    ]

    main_image = product.get("image")

    if main_image and main_image not in product_images:
        product_images.insert(0, main_image)

        # -----------------------------------------
    # PRODUCT SIZE
    # -----------------------------------------

    category = str(product.get("category", "")).lower()
    name = str(product.get("name", "")).lower()

    if (
        "jeans" in category
        or "pants" in category
        or "pant" in category
        or "track" in category
        or "jeans" in name
        or "pants" in name
        or "pant" in name
    ):
        product_sizes = ["30", "32", "36", "38"]

    else:
        product_sizes = ["M", "L", "XL", "XXL"]

    return render_template(
        "products-details.html",
        product=product,
        product_images=product_images,
        product_sizes=product_sizes
    )

    # ========================================================
    # REVIEWS
    # ========================================================

    reviews = get_product_reviews(product_id)

    rating_summary, rating_breakdown = (
        get_product_rating_summary(product_id)
    )

    review_count = int(
        rating_summary["review_count"] or 0
    )

    average_rating = float(
        rating_summary["average_rating"] or 0
    )

    # ========================================================
    # REVIEW PERMISSION
    # ========================================================

    user = session.get("user")

    can_review = False
    has_reviewed = False

    if user:

        user_id = user.get("id")

        if user_id:

            can_review = user_purchased_product(
                user_id,
                product_id
            )

            has_reviewed = has_user_reviewed_product(
                user_id,
                product_id
            )

    # ========================================================
    # PAGE
    # ========================================================

    return render_template(
        "products-details.html",

        product=product,

        product_images=product_images,

        reviews=reviews,

        review_count=review_count,

        average_rating=average_rating,

        rating_breakdown=rating_breakdown,

        can_review=can_review,

        has_reviewed=has_reviewed
    )


# =====================================================
# WISHLIST
# =====================================================

@app.route("/wishlist")
def wishlist():

    ids_text = request.args.get(
        "ids",
        ""
    )

    ids = []

    if ids_text:

        for value in ids_text.split(","):

            if value.strip().isdigit():

                ids.append(
                    int(value.strip())
                )

    wishlist_products = []

    for product_id in ids:

        product = get_product_from_db(
            product_id
        )

        if product:

            wishlist_products.append(
                product
            )

    return render_template(
        "wishlist.html",
        products=wishlist_products
    )


# =====================================================
# ADD TO CART
# =====================================================

@app.route(
    "/add-to-cart",
    methods=["POST"]
)
def add_to_cart():

    try:

        product_id = int(
            request.form.get(
                "product_id"
            )
        )

    except (TypeError, ValueError):

        flash(
            "Invalid product.",
            "error"
        )

        return redirect(
            url_for("products")
        )

    size = request.form.get(
        "size",
        ""
    ).strip().upper()

    try:

        quantity = int(
            request.form.get(
                "quantity",
                1
            )
        )

    except (TypeError, ValueError):

        quantity = 1

    if size not in VALID_SIZES:

        flash(
            "Please select a size before adding the product to cart.",
            "error"
        )

        return redirect(
            request.referrer
            or url_for("products")
        )

    if quantity < 1:
        quantity = 1

    product = get_product_from_db(
        product_id
    )

    if product is None:

        return (
            "Product not found",
            404
        )

    stock = int(
        product.get("stock") or 0
    )

    if stock <= 0:

        flash(
            "This product is currently out of stock.",
            "error"
        )

        return redirect(
            request.referrer
            or url_for("products")
        )

    cart = session.get(
        "cart",
        []
    )

    found = False

    for item in cart:

        if (
            item.get("product_id")
            == product_id
            and item.get("size")
            == size
        ):

            new_quantity = (
                int(item.get("quantity", 1))
                + quantity
            )

            if new_quantity > stock:

                flash(
                    f"Only {stock} item(s) are available in stock.",
                    "error"
                )

                return redirect(
                    request.referrer
                    or url_for("products")
                )

            item["quantity"] = (
                new_quantity
            )

            found = True

            break

    if not found:

        if quantity > stock:

            flash(
                f"Only {stock} item(s) are available in stock.",
                "error"
            )

            return redirect(
                request.referrer
                or url_for("products")
            )

        cart.append(
            {
                "product_id": product_id,
                "size": size,
                "quantity": quantity
            }
        )

    session["cart"] = cart
    session.modified = True

    flash(
        f"{product['name']} ({size}) added to cart!",
        "success"
    )

    return redirect(
        url_for("cart")
    )


# =====================================================
# CART
# =====================================================

@app.route("/cart")
def cart():

    cart_data = calculate_cart()

    return render_template(
        "cart.html",
        cart_items=cart_data["cart_items"],
        original_subtotal=cart_data[
            "original_subtotal"
        ],
        discount_total=cart_data[
            "discount_total"
        ],
        subtotal=cart_data["subtotal"],
        delivery_charge=cart_data[
            "delivery_charge"
        ],
        delivery_text=cart_data[
            "delivery_text"
        ],
        grand_total=cart_data["grand_total"],
        free_delivery_limit=cart_data[
            "free_delivery_limit"
        ]
    )


# =====================================================
# UPDATE CART
# =====================================================

@app.route(
    "/update-cart/<int:index>",
    methods=["POST"]
)
def update_cart(index):

    try:

        quantity = int(
            request.form.get(
                "quantity",
                1
            )
        )

    except (TypeError, ValueError):

        quantity = 1

    size = request.form.get(
        "size",
        ""
    ).strip().upper()

    cart = session.get(
        "cart",
        []
    )

    if 0 <= index < len(cart):

        product_id = cart[index].get(
            "product_id"
        )

        product = get_product_from_db(
            product_id
        )

        if not product:

            cart.pop(index)

        elif quantity <= 0:

            cart.pop(index)

        else:

            stock = int(
                product.get("stock") or 0
            )

            if stock <= 0:

                cart.pop(index)

            else:

                if quantity > stock:

                    flash(
                        f"Only {stock} item(s) are available.",
                        "error"
                    )

                    quantity = stock

                cart[index]["quantity"] = (
                    quantity
                )

                if size in VALID_SIZES:

                    cart[index]["size"] = (
                        size
                    )

    session["cart"] = cart
    session.modified = True

    return redirect(
        url_for("cart")
    )


# =====================================================
# REMOVE FROM CART
# =====================================================

@app.route(
    "/remove-from-cart/<int:index>"
)
def remove_from_cart(index):

    cart = session.get(
        "cart",
        []
    )

    if 0 <= index < len(cart):

        cart.pop(index)

    session["cart"] = cart
    session.modified = True

    return redirect(
        url_for("cart")
    )


# =====================================================
# CHECKOUT
# =====================================================

@app.route("/checkout")
def checkout():

    if not session.get("user"):

        flash(
            "Please login before checkout.",
            "error"
        )

        return redirect(
            url_for("login")
        )

    cart_data = calculate_cart()

    if not cart_data["cart_items"]:

        flash(
            "Your cart is empty.",
            "error"
        )

        return redirect(
            url_for("products")
        )

    return render_template(
        "checkout.html",
        cart_items=cart_data[
            "cart_items"
        ],
        original_subtotal=cart_data[
            "original_subtotal"
        ],
        discount_total=cart_data[
            "discount_total"
        ],
        subtotal=cart_data["subtotal"],
        delivery_charge=cart_data[
            "delivery_charge"
        ],
        grand_total=cart_data[
            "grand_total"
        ],
        free_delivery_limit=cart_data[
            "free_delivery_limit"
        ]
    )


# =====================================================
# PLACE ORDER
# =====================================================

@app.route(
    "/place-order",
    methods=["POST"]
)
def place_order():

    if not session.get("user"):

        flash(
            "Please login before placing an order.",
            "error"
        )

        return redirect(
            url_for("login")
        )

    cart_data = calculate_cart()
    cart_items = cart_data["cart_items"]

    if not cart_items:

        flash(
            "Your cart is empty.",
            "error"
        )

        return redirect(
            url_for("products")
        )

    name = request.form.get(
        "name",
        ""
    ).strip()

    phone = request.form.get(
        "phone",
        ""
    ).strip()

    address = request.form.get(
        "address",
        ""
    ).strip()

    city = request.form.get(
        "city",
        ""
    ).strip()

    pincode = request.form.get(
        "pincode",
        ""
    ).strip()

    # =================================================
    # ONLINE PAYMENT ONLY - UPI
    # =================================================

    payment_method = request.form.get(
        "payment_method",
        "upi"
    ).strip().lower()

    # Cash on Delivery is permanently disabled.
    if payment_method != "upi":

        flash(
            "Online UPI payment is required. Cash on Delivery is not available.",
            "error"
        )

        return redirect(
            url_for("checkout")
        )

    # The checkout page asks the customer to confirm that
    # the UPI payment was completed before an order is created.
    # This is a customer confirmation only; it is NOT automatic
    # bank/payment-gateway verification.
    payment_confirmed = request.form.get(
        "payment_confirmed",
        ""
    )

    if payment_confirmed != "1":

        flash(
            "Please complete the UPI payment and confirm it before placing the order.",
            "error"
        )

        return redirect(
            url_for("checkout")
        )

    if not all(
        [
            name,
            phone,
            address,
            city,
            pincode
        ]
    ):

        flash(
            "Please fill in all delivery details.",
            "error"
        )

        return redirect(
            url_for("checkout")
        )

    user = session.get(
        "user",
        {}
    )

    user_id = user.get(
        "id"
    )

    connection = get_db_connection()
    cursor = connection.cursor(
        dictionary=True
    )

    order_id = None

    try:

        # ---------------------------------------------
        # Re-check stock
        # ---------------------------------------------

        for item in cart_items:

            cursor.execute(
                """
                SELECT
                    id,
                    name,
                    stock,
                    price,
                    discount
                FROM products
                WHERE id = %s
                """,
                (
                    item["product"]["id"],
                )
            )

            current_product = (
                cursor.fetchone()
            )

            if not current_product:

                connection.rollback()

                flash(
                    f"{item['product']['name']} is no longer available.",
                    "error"
                )

                return redirect(
                    url_for("cart")
                )

            current_stock = int(
                current_product.get("stock")
                or 0
            )

            requested_quantity = (
                item["quantity"]
            )

            if requested_quantity > current_stock:

                connection.rollback()

                flash(
                    f"Only {current_stock} of "
                    f"{current_product['name']} are available.",
                    "error"
                )

                return redirect(
                    url_for("cart")
                )

        # ---------------------------------------------
        # Create order
        # ---------------------------------------------

        cursor.execute(
            """
            INSERT INTO orders
            (
                user_id,
                name,
                phone,
                address,
                city,
                pincode,
                payment_method,
                original_subtotal,
                discount_total,
                subtotal,
                delivery_charge,
                total,
                status
            )
            VALUES
            (
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s
            )
            """,
            (
                user_id,
                name,
                phone,
                address,
                city,
                pincode,
                payment_method,
                cart_data[
                    "original_subtotal"
                ],
                cart_data[
                    "discount_total"
                ],
                cart_data[
                    "subtotal"
                ],
                cart_data[
                    "delivery_charge"
                ],
                cart_data[
                    "grand_total"
                ],
                "Pending"
            )
        )

        order_id = cursor.lastrowid

        # ---------------------------------------------
        # Order items + decrease stock
        # ---------------------------------------------

        for item in cart_items:

            product = item["product"]

            cursor.execute(
                """
                INSERT INTO order_items
                (
                    order_id,
                    product_id,
                    product_name,
                    size,
                    quantity,
                    original_price,
                    discount_percent,
                    discount_amount,
                    final_price,
                    total
                )
                VALUES
                (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                )
                """,
                (
                    order_id,
                    product["id"],
                    product["name"],
                    item["size"],
                    item["quantity"],
                    item["original_price"],
                    item["discount_percent"],
                    item["discount_amount"],
                    item["final_price"],
                    item["total"]
                )
            )

            cursor.execute(
                """
                UPDATE products
                SET stock = stock - %s
                WHERE id = %s
                """,
                (
                    item["quantity"],
                    product["id"]
                )
            )

        connection.commit()

        session["cart"] = []
        session["last_order_id"] = (
            order_id
        )
        session.modified = True

    except Exception:

        connection.rollback()

        raise

    finally:

        cursor.close()
        connection.close()

    return redirect(
        url_for(
            "order_success",
            order_id=order_id
        )
    )


# =====================================================
# ORDER SUCCESS
# =====================================================

@app.route(
    "/order-success/<int:order_id>"
)
def order_success(order_id):

    user = session.get(
        "user"
    )

    if not user:

        flash(
            "Please login first.",
            "error"
        )

        return redirect(
            url_for("login")
        )

    connection = get_db_connection()
    cursor = connection.cursor(
        dictionary=True
    )

    try:

        cursor.execute(
            """
            SELECT *
            FROM orders
            WHERE id = %s
              AND user_id = %s
            """,
            (
                order_id,
                user.get("id")
            )
        )

        order = cursor.fetchone()

        if not order:

            return (
                "Order not found",
                404
            )

        cursor.execute(
            """
            SELECT
                product_name AS name,
                original_price AS price,
                discount_percent,
                discount_amount,
                final_price,
                quantity,
                size,
                total
            FROM order_items
            WHERE order_id = %s
            ORDER BY id ASC
            """,
            (
                order_id,
            )
        )

        order["items"] = (
            cursor.fetchall()
        )

    finally:

        cursor.close()
        connection.close()

    return render_template(
        "order-success.html",
        order=order
    )


# =====================================================
# CUSTOMER ORDERS
# =====================================================

@app.route("/orders")
def orders():

    user = session.get(
        "user"
    )

    if not user:

        flash(
            "Please login first.",
            "error"
        )

        return redirect(
            url_for("login")
        )

    connection = get_db_connection()
    cursor = connection.cursor(
        dictionary=True
    )

    try:

        cursor.execute(
            """
            SELECT *
            FROM orders
            WHERE user_id = %s
            ORDER BY
                created_at DESC,
                id DESC
            """,
            (
                user.get("id"),
            )
        )

        orders_data = cursor.fetchall()

        for order in orders_data:

            order["order_id"] = (
                order["id"]
            )

            cursor.execute(
                """
                SELECT
                    product_name AS name,
                    original_price AS price,
                    discount_percent,
                    discount_amount,
                    final_price,
                    quantity,
                    size,
                    total
                FROM order_items
                WHERE order_id = %s
                ORDER BY id ASC
                """,
                (
                    order["id"],
                )
            )

            order["items"] = (
                cursor.fetchall()
            )

    finally:

        cursor.close()
        connection.close()

    return render_template(
        "orders.html",
        orders=orders_data
    )


# =====================================================
# CUSTOMER LOGIN
# =====================================================

@app.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    if request.method == "POST":

        email = request.form.get(
            "email",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        connection = get_db_connection()
        cursor = connection.cursor(
            dictionary=True
        )

        try:

            cursor.execute(
                """
                SELECT
                    id,
                    name,
                    email,
                    password,
                    created_at
                FROM users
                WHERE LOWER(email) = LOWER(%s)
                LIMIT 1
                """,
                (
                    email,
                )
            )

            user = cursor.fetchone()

        finally:

            cursor.close()
            connection.close()

        if (
            user
            and user["password"] == password
        ):

            session["registered_user"] = (
                user
            )

            session["user"] = {
                "id": user["id"],
                "name": user["name"],
                "email": user["email"],
                "created_at": user["created_at"]
            }

            flash(
                "Login successful! Welcome to Neon Clothing.",
                "success"
            )

            return redirect(
                url_for("profile")
            )

        flash(
            "Invalid email or password.",
            "error"
        )

        return redirect(
            url_for("login")
        )

    return render_template(
        "login.html"
    )


# =====================================================
# CUSTOMER REGISTER
# =====================================================

@app.route(
    "/register",
    methods=["GET", "POST"]
)
def register():

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        email = request.form.get(
            "email",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        confirm_password = request.form.get(
            "confirm_password",
            ""
        )

        if (
            not name
            or not email
            or not password
            or not confirm_password
        ):

            flash(
                "Please fill in all required fields.",
                "error"
            )

            return redirect(
                url_for("register")
            )

        if password != confirm_password:

            flash(
                "Passwords do not match.",
                "error"
            )

            return redirect(
                url_for("register")
            )

        if len(password) < 6:

            flash(
                "Password must contain at least 6 characters.",
                "error"
            )

            return redirect(
                url_for("register")
            )

        connection = get_db_connection()
        cursor = connection.cursor(
            dictionary=True
        )

        try:

            cursor.execute(
                """
                SELECT id
                FROM users
                WHERE LOWER(email) = LOWER(%s)
                LIMIT 1
                """,
                (
                    email,
                )
            )

            existing_user = (
                cursor.fetchone()
            )

            if existing_user:

                flash(
                    "Email already registered. Please login.",
                    "error"
                )

                return redirect(
                    url_for("login")
                )

            cursor.execute(
                """
                INSERT INTO users
                (
                    name,
                    email,
                    password
                )
                VALUES
                (
                    %s,
                    %s,
                    %s
                )
                """,
                (
                    name,
                    email,
                    password
                )
            )

            user_id = (
                cursor.lastrowid
            )

            connection.commit()

            new_user = {
                "id": user_id,
                "name": name,
                "email": email
            }

            session["registered_user"] = (
                new_user
            )

            flash(
                "Account created successfully! Please login.",
                "success"
            )

            return redirect(
                url_for("login")
            )

        except Exception:

            connection.rollback()

            raise

        finally:

            cursor.close()
            connection.close()

    return render_template(
        "register.html"
    )


# =====================================================
# CONTACT
# =====================================================

@app.route(
    "/contact",
    methods=["GET", "POST"]
)
def contact():

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        email = request.form.get(
            "email",
            ""
        ).strip()

        phone = request.form.get(
            "phone",
            ""
        ).strip()

        subject = request.form.get(
            "subject",
            ""
        ).strip()

        message = request.form.get(
            "message",
            ""
        ).strip()

        if (
            not name
            or not email
            or not subject
            or not message
        ):

            flash(
                "Please fill in all required fields.",
                "error"
            )

            return redirect(
                url_for("contact")
            )

        flash(
            "Thank you! Your message has been sent successfully.",
            "success"
        )

        return redirect(
            url_for("contact")
        )

    return render_template(
        "contact.html"
    )


# =====================================================
# ADMIN LOGIN
# =====================================================

@app.route(
    "/admin-login",
    methods=["GET", "POST"]
)
def admin_login():

    if session.get(
        "admin_logged_in"
    ):

        return redirect(
            url_for("admin_dashboard")
        )

    if request.method == "POST":

        email = request.form.get(
            "email",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        if (
            email.lower()
            == ADMIN_EMAIL.lower()
            and password
            == ADMIN_PASSWORD
        ):

            session["admin_logged_in"] = (
                True
            )

            flash(
                "Admin login successful!",
                "success"
            )

            return redirect(
                url_for("admin_dashboard")
            )

        flash(
            "Invalid admin email or password.",
            "error"
        )

        return redirect(
            url_for("admin_login")
        )

    return render_template(
        "admin-login.html"
    )


# =====================================================
# ADMIN LOGOUT
# =====================================================

@app.route("/admin-logout")
def admin_logout():

    session.pop(
        "admin_logged_in",
        None
    )

    flash(
        "Admin logged out successfully.",
        "success"
    )

    return redirect(
        url_for("home")
    )


# =====================================================
# ADMIN DASHBOARD
# =====================================================

@app.route("/admin")
@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():

    template_path = os.path.join(
        BASE_DIR,
        "admin",
        "dashboard.html"
    )

    if not os.path.isfile(template_path):

        return (
            f"""
            <h2>Admin Dashboard File Not Found</h2>
            <p>Flask is looking for:</p>
            <p><strong>{template_path}</strong></p>
            """,
            404
        )

    connection = get_db_connection()
    cursor = connection.cursor(
        dictionary=True
    )

    try:

        # =================================================
        # TOTAL SALES
        # =================================================

        cursor.execute(
            """
            SELECT
                COALESCE(SUM(total), 0) AS total_sales
            FROM orders
            """
        )

        total_sales = float(
            cursor.fetchone()["total_sales"] or 0
        )


        # =================================================
        # TOTAL ORDERS
        # =================================================

        cursor.execute(
            """
            SELECT
                COUNT(*) AS total_orders
            FROM orders
            """
        )

        total_orders = int(
            cursor.fetchone()["total_orders"] or 0
        )


        # =================================================
        # TOTAL PRODUCTS
        # =================================================

        cursor.execute(
            """
            SELECT
                COUNT(*) AS total_products
            FROM products
            """
        )

        total_products = int(
            cursor.fetchone()["total_products"] or 0
        )


        # =================================================
        # TOTAL CUSTOMERS
        # =================================================

        cursor.execute(
            """
            SELECT
                COUNT(*) AS total_customers
            FROM users
            """
        )

        total_customers = int(
            cursor.fetchone()["total_customers"] or 0
        )


        # =================================================
        # PENDING ORDERS
        # =================================================

        cursor.execute(
            """
            SELECT
                COUNT(*) AS pending_orders
            FROM orders
            WHERE status = 'Pending'
            """
        )

        pending_orders = int(
            cursor.fetchone()["pending_orders"] or 0
        )


        # =================================================
        # LOW STOCK PRODUCTS
        # =================================================

        cursor.execute(
            """
            SELECT
                COUNT(*) AS low_stock_products
            FROM products
            WHERE stock <= 5
            """
        )

        low_stock_products = int(
            cursor.fetchone()["low_stock_products"] or 0
        )


        # =================================================
        # RECENT ORDERS
        # =================================================

        cursor.execute(
            """
            SELECT
                id,
                name,
                phone,
                total,
                status,
                created_at
            FROM orders
            ORDER BY
                created_at DESC,
                id DESC
            LIMIT 5
            """
        )

        recent_orders = cursor.fetchall()


    finally:

        cursor.close()
        connection.close()


    # =================================================
    # READ DASHBOARD HTML
    # =================================================

    with open(
        template_path,
        "r",
        encoding="utf-8"
    ) as file:

        html = file.read()


    # =================================================
    # SEND LIVE DATA TO DASHBOARD
    # =================================================

    return render_template_string(
        html,

        total_sales=total_sales,

        total_orders=total_orders,

        total_products=total_products,

        total_customers=total_customers,

        pending_orders=pending_orders,

        low_stock_products=low_stock_products,

        recent_orders=recent_orders
    )


# =====================================================
# ADMIN PRODUCTS
# =====================================================

@app.route("/admin/products")
@admin_required
def admin_products():

    template_path = os.path.join(
        BASE_DIR,
        "admin",
        "products.html"
    )

    if not os.path.isfile(
        template_path
    ):

        return (
            f"""
            <h2>Admin Products File Not Found</h2>
            <p>Flask is looking for:</p>
            <p><strong>{template_path}</strong></p>
            """,
            404
        )

    products_data = (
        get_products_from_db()
    )

    with open(
        template_path,
        "r",
        encoding="utf-8"
    ) as file:

        html = file.read()

    return render_template_string(
        html,
        products=products_data,
        categories=MAIN_CATEGORIES,
        product_types=PRODUCT_TYPES
    )


# =====================================================
# ADMIN EDIT PRODUCT
# =====================================================

@app.route(
    "/admin/edit-product/<int:product_id>",
    methods=["GET", "POST"]
)
@admin_required
def admin_edit_product(product_id):

    product = get_product_from_db(
        product_id
    )

    if product is None:

        flash(
            "Product not found.",
            "error"
        )

        return redirect(
            url_for("admin_products")
        )

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        category = request.form.get(
            "category",
            ""
        ).strip()

        subcategory = request.form.get(
            "subcategory",
            ""
        ).strip()

        price_text = request.form.get(
            "price",
            "0"
        ).strip()

        discount_text = request.form.get(
            "discount",
            "0"
        ).strip()

        stock_text = request.form.get(
            "stock",
            "0"
        ).strip()

        description = request.form.get(
            "description",
            ""
        ).strip()

        # New uploaded image
        image_file = request.files.get(
            "image_file"
        )

        # Old image field from previous edit page
        old_image_input = request.form.get(
            "image",
            ""
        ).strip()

        if not name or not category:

            flash(
                "Please enter product name and category.",
                "error"
            )

            return redirect(
                url_for(
                    "admin_edit_product",
                    product_id=product_id
                )
            )

        try:

            price = float(
                price_text
            )

            discount = float(
                discount_text
            )

            stock = int(
                stock_text
            )

        except ValueError:

            flash(
                "Please enter valid price, discount and stock values.",
                "error"
            )

            return redirect(
                url_for(
                    "admin_edit_product",
                    product_id=product_id
                )
            )

        if price <= 0:

            flash(
                "Price must be greater than 0.",
                "error"
            )

            return redirect(
                url_for(
                    "admin_edit_product",
                    product_id=product_id
                )
            )

        if discount < 0 or discount > 100:

            flash(
                "Discount must be between 0% and 100%.",
                "error"
            )

            return redirect(
                url_for(
                    "admin_edit_product",
                    product_id=product_id
                )
            )

        if stock < 0:

            flash(
                "Stock cannot be negative.",
                "error"
            )

            return redirect(
                url_for(
                    "admin_edit_product",
                    product_id=product_id
                )
            )

        connection = get_db_connection()
        cursor = connection.cursor(
            dictionary=True
        )

        new_filesystem_path = None

        try:

            category_id = get_category_id(
                category,
                cursor
            )

            # -----------------------------------------
            # Image handling
            # -----------------------------------------

            new_image_path = (
                product.get("image")
            )

            if (
                image_file
                and image_file.filename
            ):

                try:

                    uploaded_db_path, uploaded_fs_path = (
                        save_product_image(
                            image_file
                        )
                    )

                    new_image_path = (
                        uploaded_db_path
                    )

                    new_filesystem_path = (
                        uploaded_fs_path
                    )

                except ValueError as error:

                    flash(
                        str(error),
                        "error"
                    )

                    return redirect(
                        url_for(
                            "admin_edit_product",
                            product_id=product_id
                        )
                    )

            elif old_image_input:

                # Supports older edit-product.htm pages
                # that still have a normal image text field.
                new_image_path = (
                    old_image_input
                )

            cursor.execute(
                """
                UPDATE products
                SET
                    name = %s,
                    category_id = %s,
                    subcategory = %s,
                    price = %s,
                    discount = %s,
                    stock = %s,
                    image = %s,
                    description = %s
                WHERE id = %s
                """,
                (
                    name,
                    category_id,
                    subcategory,
                    price,
                    discount,
                    stock,
                    new_image_path,
                    description,
                    product_id
                )
            )

            connection.commit()

        except Exception:

            connection.rollback()

            if (
                new_filesystem_path
                and os.path.isfile(
                    new_filesystem_path
                )
            ):

                try:
                    os.remove(
                        new_filesystem_path
                    )
                except OSError:
                    pass

            raise

        finally:

            cursor.close()
            connection.close()

        # Delete previous local image only after DB update succeeds
        previous_image = product.get(
            "image"
        )

        if (
            new_image_path
            and previous_image
            and new_image_path
            != previous_image
        ):

            delete_local_product_image(
                previous_image
            )

        flash(
            f"{name} updated successfully!",
            "success"
        )

        return redirect(
            url_for("admin_products")
        )

    # ---------------------------------------------
    # Find edit-product file
    # ---------------------------------------------

    admin_folder = os.path.join(
        BASE_DIR,
        "admin"
    )

    possible_files = [
        "edit-product.htm",
        "edit-product.html"
    ]

    template_path = None

    for filename in possible_files:

        test_path = os.path.join(
            admin_folder,
            filename
        )

        if os.path.isfile(
            test_path
        ):

            template_path = test_path

            break

    if template_path is None:

        return (
            f"""
            <h2>Edit Product File Not Found</h2>
            <p>Flask checked:</p>
            <p><strong>{admin_folder}</strong></p>
            <ul>
                <li>edit-product.htm</li>
                <li>edit-product.html</li>
            </ul>
            """,
            404
        )

    with open(
        template_path,
        "r",
        encoding="utf-8"
    ) as file:

        html = file.read()

    return render_template_string(
        html,
        product=product,
        categories=MAIN_CATEGORIES,
        product_types=PRODUCT_TYPES
    )


# =====================================================
# ADMIN DELETE PRODUCT
# =====================================================

@app.route(
    "/admin/delete-product/<int:product_id>",
    methods=["GET"]
)
@admin_required
def admin_delete_product(product_id):

    product = get_product_from_db(
        product_id
    )

    if product is None:

        flash(
            "Product not found.",
            "error"
        )

        return redirect(
            url_for("admin_products")
        )

    connection = get_db_connection()
    cursor = connection.cursor()

    try:

        cursor.execute(
            """
            DELETE FROM products
            WHERE id = %s
            """,
            (
                product_id,
            )
        )

        connection.commit()

    except Exception:

        connection.rollback()

        flash(
            "This product cannot be deleted because it may already be used in an order.",
            "error"
        )

        return redirect(
            url_for("admin_products")
        )

    finally:

        cursor.close()
        connection.close()

    # Delete local image after successful deletion
    delete_local_product_image(
        product.get("image")
    )

    flash(
        f"{product['name']} deleted successfully!",
        "success"
    )

    return redirect(
        url_for("admin_products")
    )


# =====================================================
# ADMIN ADD PRODUCT
# =====================================================

@app.route(
    "/admin/add-products",
    methods=["GET", "POST"]
)
@admin_required
def admin_add_product():

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        category = request.form.get(
            "category",
            ""
        ).strip()

        subcategory = request.form.get(
            "subcategory",
            ""
        ).strip()

        price_text = request.form.get(
            "price",
            "0"
        ).strip()

        discount_text = request.form.get(
            "discount",
            "0"
        ).strip()

        stock_text = request.form.get(
            "stock",
            "0"
        ).strip()

        description = request.form.get(
            "description",
            ""
        ).strip()

        # ---------------------------------------------
        # MULTIPLE PRODUCT IMAGES
        # ---------------------------------------------

        image_files = request.files.getlist(
            "image_files"
        )

        # Keep only actual selected files.
        image_files = [
            image_file
            for image_file in image_files
            if image_file
            and image_file.filename
        ]

        # ---------------------------------------------
        # Validate fields
        # ---------------------------------------------

        if (
            not name
            or not category
            or not subcategory
            or not price_text
            or not description
        ):

            flash(
                "Please fill in all required product fields.",
                "error"
            )

            return redirect(
                url_for("admin_add_product")
            )

        # At least one image is required.
        # There is NO maximum image count.
        if not image_files:

            flash(
                "Please select at least one product photo.",
                "error"
            )

            return redirect(
                url_for("admin_add_product")
            )

        # ---------------------------------------------
        # Validate numbers
        # ---------------------------------------------

        try:

            price = float(
                price_text
            )

            discount = float(
                discount_text
            )

            stock = int(
                stock_text
            )

        except ValueError:

            flash(
                "Please enter valid price, discount and stock values.",
                "error"
            )

            return redirect(
                url_for("admin_add_product")
            )

        if price <= 0:

            flash(
                "Price must be greater than 0.",
                "error"
            )

            return redirect(
                url_for("admin_add_product")
            )

        if discount < 0 or discount > 100:

            flash(
                "Discount must be between 0% and 100%.",
                "error"
            )

            return redirect(
                url_for("admin_add_product")
            )

        if stock < 0:

            flash(
                "Stock cannot be negative.",
                "error"
            )

            return redirect(
                url_for("admin_add_product")
            )

        # ---------------------------------------------
        # Validate all selected images
        # ---------------------------------------------

        for image_file in image_files:

            if not is_allowed_image(
                image_file.filename
            ):

                flash(
                    "Only JPG, JPEG, PNG and WEBP images are allowed.",
                    "error"
                )

                return redirect(
                    url_for("admin_add_product")
                )

        # ---------------------------------------------
        # Save ALL images locally
        # ---------------------------------------------

        saved_images = []

        try:

            for image_file in image_files:

                uploaded_db_path, uploaded_filesystem_path = (
                    save_product_image(
                        image_file
                    )
                )

                saved_images.append(
                    (
                        uploaded_db_path,
                        uploaded_filesystem_path
                    )
                )

        except ValueError as error:

            for _, filesystem_path in saved_images:

                if (
                    filesystem_path
                    and os.path.isfile(filesystem_path)
                ):

                    try:
                        os.remove(filesystem_path)
                    except OSError:
                        pass

            flash(
                str(error),
                "error"
            )

            return redirect(
                url_for("admin_add_product")
            )

        except Exception:

            for _, filesystem_path in saved_images:

                if (
                    filesystem_path
                    and os.path.isfile(filesystem_path)
                ):

                    try:
                        os.remove(filesystem_path)
                    except OSError:
                        pass

            raise

        # ---------------------------------------------
        # Insert product + gallery images
        # ---------------------------------------------

        connection = get_db_connection()
        cursor = connection.cursor(
            dictionary=True
        )

        try:

            category_id = get_category_id(
                category,
                cursor
            )

            # FIRST image becomes the main product image.
            main_image = saved_images[0][0]

            cursor.execute(
                """
                INSERT INTO products
                (
                    name,
                    category_id,
                    subcategory,
                    price,
                    discount,
                    stock,
                    image,
                    description
                )
                VALUES
                (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                )
                """,
                (
                    name,
                    category_id,
                    subcategory,
                    price,
                    discount,
                    stock,
                    main_image,
                    description
                )
            )

            product_id = cursor.lastrowid

            # Save EVERY selected image in product_images.
            for database_path, _ in saved_images:

                cursor.execute(
                    """
                    INSERT INTO product_images
                    (
                        product_id,
                        image_path
                    )
                    VALUES
                    (
                        %s,
                        %s
                    )
                    """,
                    (
                        product_id,
                        database_path
                    )
                )

            connection.commit()

        except Exception:

            connection.rollback()

            for _, filesystem_path in saved_images:

                if (
                    filesystem_path
                    and os.path.isfile(filesystem_path)
                ):

                    try:
                        os.remove(filesystem_path)
                    except OSError:
                        pass

            raise

        finally:

            cursor.close()
            connection.close()

        flash(
            f"{name} added successfully with {len(saved_images)} photo(s)!",
            "success"
        )

        return redirect(
            url_for("admin_products")
        )

    # ---------------------------------------------
    # Find add product file
    # ---------------------------------------------

    admin_folder = os.path.join(
        BASE_DIR,
        "admin"
    )

    possible_files = [
        "add-products.html",
        "add-product.html",
        "add-product.htm",
        "add-product.shtml"
    ]

    template_path = next(
        (
            os.path.join(
                admin_folder,
                filename
            )
            for filename in possible_files
            if os.path.isfile(
                os.path.join(
                    admin_folder,
                    filename
                )
            )
        ),
        None
    )

    if template_path is None:

        return (
            f"""
            <h2>Admin Add Product File Not Found</h2>
            <p>Flask is checking:</p>
            <p><strong>{admin_folder}</strong></p>
            """,
            404
        )

    with open(
        template_path,
        "r",
        encoding="utf-8"
    ) as file:

        html = file.read()

    return render_template_string(
        html,
        categories=MAIN_CATEGORIES,
        product_types=PRODUCT_TYPES
    )


# =====================================================
# ADMIN USERS
# =====================================================

@app.route("/admin/users")
@admin_required
def admin_users():

    template_path = os.path.join(
        BASE_DIR,
        "admin",
        "users.html"
    )

    if not os.path.isfile(
        template_path
    ):

        return (
            f"""
            <h2>Admin Users File Not Found</h2>
            <p>Flask is looking for:</p>
            <p><strong>{template_path}</strong></p>
            """,
            404
        )

    connection = get_db_connection()
    cursor = connection.cursor(
        dictionary=True
    )

    try:

        cursor.execute(
            """
            SELECT
                id,
                name,
                email,
                created_at
            FROM users
            ORDER BY id DESC
            """
        )

        users = cursor.fetchall()

    finally:

        cursor.close()
        connection.close()

    with open(
        template_path,
        "r",
        encoding="utf-8"
    ) as file:

        html = file.read()

    return render_template_string(
        html,
        users=users
    )


# =====================================================
# ADMIN DELETE USER
# =====================================================

@app.route(
    "/admin/delete-user/<int:user_id>"
)
@admin_required
def admin_delete_user(user_id):

    connection = get_db_connection()
    cursor = connection.cursor(
        dictionary=True
    )

    try:

        cursor.execute(
            """
            SELECT
                id,
                name,
                email
            FROM users
            WHERE id = %s
            """,
            (
                user_id,
            )
        )

        user = cursor.fetchone()

        if not user:

            flash(
                "User not found.",
                "error"
            )

            return redirect(
                url_for("admin_users")
            )

        cursor.execute(
            """
            DELETE FROM users
            WHERE id = %s
            """,
            (
                user_id,
            )
        )

        connection.commit()

    except Exception:

        connection.rollback()

        flash(
            "Unable to delete this user.",
            "error"
        )

        return redirect(
            url_for("admin_users")
        )

    finally:

        cursor.close()
        connection.close()

    current_user = session.get(
        "user"
    )

    if (
        current_user
        and current_user.get("id")
        == user_id
    ):

        session.pop(
            "user",
            None
        )

        session.pop(
            "registered_user",
            None
        )

    flash(
        f"{user['name']} deleted successfully!",
        "success"
    )

    return redirect(
        url_for("admin_users")
    )


# =====================================================
# ADMIN ORDERS
# =====================================================

@app.route("/admin/orders")
@admin_required
def admin_orders():

    template_path = os.path.join(
        BASE_DIR,
        "admin",
        "orders.html"
    )

    if not os.path.isfile(
        template_path
    ):

        return (
            f"""
            <h2>Admin Orders File Not Found</h2>
            <p>Flask is looking for:</p>
            <p><strong>{template_path}</strong></p>
            """,
            404
        )

    connection = get_db_connection()
    cursor = connection.cursor(
        dictionary=True
    )

    try:

        cursor.execute(
            """
            SELECT *
            FROM orders
            ORDER BY
                created_at DESC,
                id DESC
            """
        )

        orders_data = (
            cursor.fetchall()
        )

        for order in orders_data:

            order["order_id"] = (
                order["id"]
            )

            cursor.execute(
                """
                SELECT
                    product_name AS name,
                    original_price AS price,
                    discount_percent,
                    discount_amount,
                    final_price,
                    quantity,
                    size,
                    total
                FROM order_items
                WHERE order_id = %s
                ORDER BY id ASC
                """,
                (
                    order["id"],
                )
            )

            order["items"] = (
                cursor.fetchall()
            )

        pending_count = sum(
            1
            for order in orders_data
            if order.get(
                "status",
                "Pending"
            ) == "Pending"
        )

        total_sales = sum(
            float(
                order.get("total")
                or 0
            )
            for order in orders_data
        )

    finally:

        cursor.close()
        connection.close()

    with open(
        template_path,
        "r",
        encoding="utf-8"
    ) as file:

        html = file.read()

    return render_template_string(
        html,
        orders=orders_data,
        pending_count=pending_count,
        total_sales=total_sales
    )


# =====================================================
# ADMIN UPDATE ORDER STATUS
# =====================================================

@app.route(
    "/admin/update-order/<int:order_id>",
    methods=["POST"]
)
@admin_required
def admin_update_order(order_id):

    new_status = request.form.get(
        "status",
        "Pending"
    ).strip()

    valid_statuses = [
        "Pending",
        "Confirmed",
        "Packed",
        "Shipped",
        "Delivered"
    ]

    if new_status not in valid_statuses:

        flash(
            "Invalid order status.",
            "error"
        )

        return redirect(
            url_for("admin_orders")
        )

    connection = get_db_connection()
    cursor = connection.cursor()

    try:

        cursor.execute(
            """
            UPDATE orders
            SET status = %s
            WHERE id = %s
            """,
            (
                new_status,
                order_id
            )
        )

        connection.commit()

        if cursor.rowcount == 0:

            flash(
                "Order not found.",
                "error"
            )

        else:

            flash(
                f"Order #{order_id} status updated to {new_status}.",
                "success"
            )

    except Exception:

        connection.rollback()

        raise

    finally:

        cursor.close()
        connection.close()

    return redirect(
        url_for("admin_orders")
    )


# =====================================================
# ADMIN CATEGORIES
# =====================================================

@app.route(
    "/admin/categories",
    methods=["GET", "POST"]
)
@admin_required
def admin_categories():

    template_path = os.path.join(
        BASE_DIR,
        "admin",
        "categories.html"
    )

    if not os.path.isfile(
        template_path
    ):

        return (
            f"""
            <h2>Admin Categories File Not Found</h2>
            <p>Flask is looking for:</p>
            <p><strong>{template_path}</strong></p>
            """,
            404
        )

    if request.method == "POST":

        category_name = request.form.get(
            "category",
            ""
        ).strip()

        if not category_name:

            flash(
                "Please enter a category name.",
                "error"
            )

            return redirect(
                url_for("admin_categories")
            )

        connection = get_db_connection()
        cursor = connection.cursor(
            dictionary=True
        )

        try:

            cursor.execute(
                """
                SELECT id
                FROM categories
                WHERE LOWER(name) = LOWER(%s)
                LIMIT 1
                """,
                (
                    category_name,
                )
            )

            existing = (
                cursor.fetchone()
            )

            if existing:

                flash(
                    "This category already exists.",
                    "error"
                )

                return redirect(
                    url_for("admin_categories")
                )

            cursor.execute(
                """
                INSERT INTO categories
                (name)
                VALUES
                (%s)
                """,
                (
                    category_name,
                )
            )

            connection.commit()

            flash(
                f"{category_name} category added successfully!",
                "success"
            )

        except Exception:

            connection.rollback()

            raise

        finally:

            cursor.close()
            connection.close()

        return redirect(
            url_for("admin_categories")
        )

    categories = get_all_categories()

    with open(
        template_path,
        "r",
        encoding="utf-8"
    ) as file:

        html = file.read()

    return render_template_string(
        html,
        categories=categories,
        product_types=PRODUCT_TYPES
    )


# =====================================================
# ADMIN DELETE CATEGORY
# =====================================================

@app.route(
    "/admin/delete-category/<path:category_name>"
)
@admin_required
def admin_delete_category(category_name):

    category_name = (
        category_name.strip()
    )

    connection = get_db_connection()
    cursor = connection.cursor(
        dictionary=True
    )

    try:

        cursor.execute(
            """
            SELECT
                c.id,
                c.name,
                COUNT(p.id) AS product_count
            FROM categories c
            LEFT JOIN products p
                ON p.category_id = c.id
            WHERE LOWER(c.name) = LOWER(%s)
            GROUP BY
                c.id,
                c.name
            """,
            (
                category_name,
            )
        )

        category = (
            cursor.fetchone()
        )

        if not category:

            flash(
                "Category not found.",
                "error"
            )

            return redirect(
                url_for("admin_categories")
            )

        if int(
            category["product_count"]
        ) > 0:

            flash(
                "Cannot delete this category because products are using it.",
                "error"
            )

            return redirect(
                url_for("admin_categories")
            )

        cursor.execute(
            """
            DELETE FROM categories
            WHERE id = %s
            """,
            (
                category["id"],
            )
        )

        connection.commit()

    except Exception:

        connection.rollback()

        raise

    finally:

        cursor.close()
        connection.close()

    flash(
        f"{category['name']} category deleted successfully!",
        "success"
    )

    return redirect(
        url_for("admin_categories")
    )


# =====================================================
# PROFILE
# =====================================================

@app.route("/profile")
def profile():

    user = session.get(
        "user"
    )

    if not user:

        flash(
            "Please login first.",
            "error"
        )

        return redirect(
            url_for("login")
        )

    return render_template(
        "profile.html",
        user=user
    )


# =====================================================
# CUSTOMER LOGOUT
# =====================================================

@app.route("/logout")
def logout():

    session.pop(
        "user",
        None
    )

    session.pop(
        "registered_user",
        None
    )

    session.pop(
        "cart",
        None
    )

    session.pop(
        "last_order_id",
        None
    )

    flash(
        "You have been logged out.",
        "success"
    )

    return redirect(
        url_for("home")
    )


# =====================================================
# SERVE PRODUCT UPLOADS
# =====================================================

@app.route(
    "/product-image/<path:filename>"
)
def product_image(filename):

    return send_from_directory(
        PRODUCT_IMAGE_FOLDER,
        filename
    )


# =====================================================
# ERROR HANDLERS
# =====================================================

@app.errorhandler(413)
def file_too_large(error):

    flash(
        "Image file is too large. Maximum size is 5 MB.",
        "error"
    )

    return redirect(
        request.referrer
        or url_for("admin_add_product")
    )

# =====================================================
# NEON CLOTHING SHOP PAGE
# =====================================================

@app.route("/shop")
@app.route("/shop/")
def shop():

    category = request.args.get(
        "category",
        "All"
    ).strip()

    subcategory = request.args.get(
        "subcategory",
        "All"
    ).strip()

    sort = request.args.get(
        "sort",
        "latest"
    ).strip()

    products_data = get_products_from_db(
        category=category,
        subcategory=subcategory
    )

    # -------------------------------------------------
    # SORT PRODUCTS
    # -------------------------------------------------

    if sort == "price-low":

        products_data.sort(
            key=lambda product: (
                float(product["price"] or 0)
                * (
                    1
                    - (
                        float(product.get("discount") or 0)
                        / 100
                    )
                )
            )
        )

    elif sort == "price-high":

        products_data.sort(
            key=lambda product: (
                float(product["price"] or 0)
                * (
                    1
                    - (
                        float(product.get("discount") or 0)
                        / 100
                    )
                )
            ),
            reverse=True
        )

    elif sort == "discount":

        products_data.sort(
            key=lambda product: float(
                product.get("discount") or 0
            ),
            reverse=True
        )

    elif sort == "name":

        products_data.sort(
            key=lambda product: (
                product.get("name") or ""
            ).lower()
        )

    else:
        # Latest
        products_data.sort(
            key=lambda product: int(
                product.get("id") or 0
            ),
            reverse=True
        )

    # -------------------------------------------------
    # BEST SELLERS
    # -------------------------------------------------

    all_products = get_products_from_db()

    best_sellers = sorted(
        all_products,
        key=lambda product: (
            float(product.get("discount") or 0),
            int(product.get("id") or 0)
        ),
        reverse=True
    )[:4]

    return render_template(
        "shop.html",
        products=products_data,
        best_sellers=best_sellers,
        categories=MAIN_CATEGORIES,
        product_types=PRODUCT_TYPES,
        selected_category=category,
        selected_subcategory=subcategory,
        selected_sort=sort
    )


# =====================================================
# KEEP OLD /products URL WORKING
# =====================================================

@app.route("/products")
def products_page_redirect():

    return redirect(
        url_for(
            "shop",
            category=request.args.get(
                "category",
                "All"
            ),
            subcategory=request.args.get(
                "subcategory",
                "All"
            )
        )
    )


# =====================================================
# TRACK ORDER
# =====================================================

@app.route(
    "/track-order",
    methods=["GET", "POST"]
)
def track_order():

    order = None
    order_items = []

    if request.method == "POST":

        order_id_text = request.form.get(
            "order_id",
            ""
        ).strip()

        phone = request.form.get(
            "phone",
            ""
        ).strip()

        try:

            order_id = int(
                order_id_text
            )

        except (TypeError, ValueError):

            flash(
                "Please enter a valid order number.",
                "error"
            )

            return redirect(
                url_for("track_order")
            )

        if not phone:

            flash(
                "Please enter the phone number used for the order.",
                "error"
            )

            return redirect(
                url_for("track_order")
            )

        connection = get_db_connection()
        cursor = connection.cursor(
            dictionary=True
        )

        try:

            cursor.execute(
                """
                SELECT *
                FROM orders
                WHERE id = %s
                  AND phone = %s
                LIMIT 1
                """,
                (
                    order_id,
                    phone
                )
            )

            order = cursor.fetchone()

            if order:

                cursor.execute(
                    """
                    SELECT
                        product_name AS name,
                        size,
                        quantity,
                        final_price,
                        total
                    FROM order_items
                    WHERE order_id = %s
                    ORDER BY id ASC
                    """,
                    (
                        order_id,
                    )
                )

                order_items = (
                    cursor.fetchall()
                )

            else:

                flash(
                    "No order found with that order number and phone number.",
                    "error"
                )

        finally:

            cursor.close()
            connection.close()

    return render_template(
        "track-order.html",
        order=order,
        order_items=order_items
    )


# =====================================================
# ABOUT US
# =====================================================

@app.route("/about-us")
@app.route("/about")
def about_us():

    return render_template(
        "about.html"
    )


# =====================================================
# OUR STORE
# =====================================================

@app.route("/our-store")
def our_store():

    return render_template(
        "our-store.html"
    )

# ============================================================
# SUBMIT PRODUCT REVIEW
# ============================================================

@app.route(
    "/product/<int:product_id>/review",
    methods=["POST"]
)
def submit_review(product_id):

    # --------------------------------------------------------
    # LOGIN CHECK
    # --------------------------------------------------------

    user = session.get("user")

    if not user:

        flash(
            "Please login to write a review.",
            "error"
        )

        return redirect(url_for(
            "login",
            next=url_for(
                "product_details",
                product_id=product_id
            )
        ))

    user_id = user.get("id")

    # --------------------------------------------------------
    # PRODUCT CHECK
    # --------------------------------------------------------

    product = get_product_from_db(product_id)

    if product is None:

        flash(
            "Product not found.",
            "error"
        )

        return redirect(url_for("shop"))

    # --------------------------------------------------------
    # RATING
    # --------------------------------------------------------

    try:

        rating = int(
            request.form.get(
                "rating",
                "0"
            )
        )

    except ValueError:

        rating = 0

    if rating < 1 or rating > 5:

        flash(
            "Please select a rating between 1 and 5 stars.",
            "error"
        )

        return redirect(
            url_for(
                "product_details",
                product_id=product_id
            ) + "#reviews"
        )

    # --------------------------------------------------------
    # REVIEW TEXT
    # --------------------------------------------------------

    review_text = request.form.get(
        "review_text",
        ""
    ).strip()

    if not review_text:

        flash(
            "Please write your review.",
            "error"
        )

        return redirect(
            url_for(
                "product_details",
                product_id=product_id
            ) + "#reviews"
        )

    if len(review_text) > 2000:

        flash(
            "Review cannot exceed 2000 characters.",
            "error"
        )

        return redirect(
            url_for(
                "product_details",
                product_id=product_id
            ) + "#reviews"
        )

    # --------------------------------------------------------
    # VERIFY PURCHASE
    # --------------------------------------------------------

    purchased = user_purchased_product(
        user_id,
        product_id
    )

    if not purchased:

        flash(
            "You can review this product after purchasing and receiving it.",
            "error"
        )

        return redirect(
            url_for(
                "product_details",
                product_id=product_id
            ) + "#reviews"
        )

    # --------------------------------------------------------
    # ONE REVIEW PER PRODUCT
    # --------------------------------------------------------

    if has_user_reviewed_product(
        user_id,
        product_id
    ):

        flash(
            "You have already reviewed this product.",
            "error"
        )

        return redirect(
            url_for(
                "product_details",
                product_id=product_id
            ) + "#reviews"
        )

    # --------------------------------------------------------
    # CUSTOMER PHOTO
    # --------------------------------------------------------

    image_path = None

    image_file = request.files.get(
        "review_image"
    )

    if image_file and image_file.filename:

        try:

            image_path = save_review_image(
                image_file
            )

        except ValueError as error:

            flash(
                str(error),
                "error"
            )

            return redirect(
                url_for(
                    "product_details",
                    product_id=product_id
                ) + "#reviews"
            )

    # --------------------------------------------------------
    # SAVE REVIEW
    # --------------------------------------------------------

    connection = get_db_connection()
    cursor = connection.cursor()

    try:

        cursor.execute("""
            INSERT INTO reviews
            (
                product_id,
                user_id,
                rating,
                review_text,
                image_path,
                is_verified
            )

            VALUES
            (
                %s,
                %s,
                %s,
                %s,
                %s,
                %s
            )
        """, (
            product_id,
            user_id,
            rating,
            review_text,
            image_path,
            1
        ))

        connection.commit()

        flash(
            "Thank you! Your review has been submitted.",
            "success"
        )

    except Exception as error:

        connection.rollback()

        # Remove uploaded photo if database insert failed
        if image_path:

            saved_file = os.path.join(
                BASE_DIR,
                "static",
                image_path
            )

            if os.path.exists(saved_file):

                try:
                    os.remove(saved_file)
                except OSError:
                    pass

        print(
            "Review submission error:",
            error
        )

        flash(
            "Unable to submit your review. Please try again.",
            "error"
        )

    finally:

        cursor.close()
        connection.close()

    return redirect(
        url_for(
            "product_details",
            product_id=product_id
        ) + "#reviews"
    )

# =====================================================
# START APPLICATION
# =====================================================

if __name__ == "__main__":

    try:

        ensure_product_subcategory_column()

        ensure_product_images_table()

        ensure_reviews_table()

        seed_database()

        os.makedirs(
            PRODUCT_IMAGE_FOLDER,
            exist_ok=True
        )

        os.makedirs(
            REVIEW_IMAGE_FOLDER,
            exist_ok=True
        )

        print(
            "NEON CLOTHING database initialized successfully."
        )

    except Exception as error:

        print(
            "MySQL connection/seed error:",
            error
        )

        print(
            "Make sure XAMPP MySQL is running "
            "and the neon_clothing database exists."
        )

    app.run(host="0.0.0.0", port=5000, debug=True)