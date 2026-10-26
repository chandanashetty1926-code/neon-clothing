
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
