"""Demo database service for SQL skill testing."""

import logging
import os
from datetime import datetime, timedelta
from random import choice, randint, uniform

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Boolean,
    create_engine,
    text,
)
from sqlalchemy.orm import declarative_base, sessionmaker

logger = logging.getLogger(__name__)

Base = declarative_base()


class Customer(Base):
    """Customer table for demo database."""

    __tablename__ = "customers"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    city = Column(String(50), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Product(Base):
    """Product table for demo database."""

    __tablename__ = "products"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    price = Column(Float, nullable=False)
    category = Column(String(50), nullable=False)
    in_stock = Column(Boolean, default=True)


class Order(Base):
    """Order table for demo database."""

    __tablename__ = "orders"

    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    total = Column(Float, nullable=False)
    order_date = Column(DateTime, default=datetime.utcnow)


# Sample data
SAMPLE_CUSTOMERS = [
    ("Alice Johnson", "alice@example.com", "New York"),
    ("Bob Smith", "bob@example.com", "Los Angeles"),
    ("Charlie Brown", "charlie@example.com", "Chicago"),
    ("Diana Prince", "diana@example.com", "San Francisco"),
    ("Eve Wilson", "eve@example.com", "Boston"),
    ("Frank Miller", "frank@example.com", "Seattle"),
    ("Grace Lee", "grace@example.com", "Austin"),
    ("Henry Davis", "henry@example.com", "Denver"),
    ("Ivy Chen", "ivy@example.com", "New York"),
    ("Jack Thompson", "jack@example.com", "Miami"),
]

SAMPLE_PRODUCTS = [
    ("Laptop Pro", 1299.99, "Electronics"),
    ("Wireless Mouse", 49.99, "Electronics"),
    ("Mechanical Keyboard", 149.99, "Electronics"),
    ("USB-C Hub", 79.99, "Electronics"),
    ("Monitor 27inch", 399.99, "Electronics"),
    ("Office Chair", 299.99, "Furniture"),
    ("Standing Desk", 599.99, "Furniture"),
    ("Desk Lamp", 45.99, "Furniture"),
    ("Coffee Maker", 89.99, "Appliances"),
    ("Blender", 69.99, "Appliances"),
]


def create_demo_database(db_url: str = "sqlite:///demo.db") -> bool:
    """Create demo database with sample tables and data.

    Args:
        db_url: Database connection string

    Returns:
        True if database was created, False if it already exists
    """
    # For SQLite, check if file exists
    if db_url.startswith("sqlite:///"):
        db_path = db_url.replace("sqlite:///", "")
        if os.path.exists(db_path):
            logger.info(f"Demo database already exists: {db_path}")
            return False

    logger.info(f"Creating demo database: {db_url}")

    # Create engine and tables
    engine = create_engine(db_url, echo=False)
    Base.metadata.create_all(engine)

    # Create session
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Add customers
        customers = []
        for name, email, city in SAMPLE_CUSTOMERS:
            customer = Customer(
                name=name,
                email=email,
                city=city,
                created_at=datetime.utcnow() - timedelta(days=randint(30, 365)),
            )
            session.add(customer)
            customers.append(customer)

        session.flush()  # Get customer IDs

        # Add products
        products = []
        for name, price, category in SAMPLE_PRODUCTS:
            product = Product(
                name=name,
                price=price,
                category=category,
                in_stock=choice([True, True, True, False]),  # 75% in stock
            )
            session.add(product)
            products.append(product)

        session.flush()  # Get product IDs

        # Add orders (random orders for each customer)
        for customer in customers:
            num_orders = randint(1, 5)
            for _ in range(num_orders):
                product = choice(products)
                quantity = randint(1, 3)
                order = Order(
                    customer_id=customer.id,
                    product_id=product.id,
                    quantity=quantity,
                    total=round(product.price * quantity, 2),
                    order_date=datetime.utcnow() - timedelta(days=randint(1, 90)),
                )
                session.add(order)

        session.commit()
        logger.info(
            f"Demo database created with {len(customers)} customers, "
            f"{len(products)} products, and orders"
        )
        return True

    except Exception as e:
        session.rollback()
        logger.error(f"Failed to create demo database: {e}")
        raise
    finally:
        session.close()


def ensure_demo_database(db_url: str = "sqlite:///demo.db") -> None:
    """Ensure demo database exists, creating it if necessary.

    Args:
        db_url: Database connection string
    """
    create_demo_database(db_url)
