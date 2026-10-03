"""Generate test images for visual matching tests"""
from PIL import Image, ImageDraw
from pathlib import Path


def create_test_images():
    """Create test images for visual similarity testing"""
    fixture_dir = Path(__file__).parent
    images_dir = fixture_dir / "images"
    images_dir.mkdir(exist_ok=True)

    # Image A: Simple red square
    img_a = Image.new("RGB", (100, 100), color="red")
    img_a.save(images_dir / "image_a.png")

    # Image A2: Same red square, resized to 150x150 then back
    img_a2 = Image.new("RGB", (100, 100), color="red")
    img_a2 = img_a2.resize((150, 150))
    img_a2 = img_a2.resize((100, 100))
    img_a2.save(images_dir / "image_a2.png")

    # Image A3: Same but with slight quality reduction
    img_a3 = Image.new("RGB", (100, 100), color="red")
    img_a3.save(images_dir / "image_a3.jpg", quality=85)
    img_a3 = Image.open(images_dir / "image_a3.jpg")
    img_a3.save(images_dir / "image_a3.png")

    # Image B: Different - blue circle
    img_b = Image.new("RGB", (100, 100), color="white")
    draw = ImageDraw.Draw(img_b)
    draw.ellipse([10, 10, 90, 90], fill="blue")
    img_b.save(images_dir / "image_b.png")

    # Image C: Different - green pattern
    img_c = Image.new("RGB", (100, 100), color="green")
    draw = ImageDraw.Draw(img_c)
    for i in range(0, 100, 10):
        draw.line([(i, 0), (i, 100)], fill="white", width=2)
    img_c.save(images_dir / "image_c.png")

    print("✓ Test images created in", images_dir)
    return {
        "image_a": str(images_dir / "image_a.png"),
        "image_a2": str(images_dir / "image_a2.png"),
        "image_a3": str(images_dir / "image_a3.png"),
        "image_b": str(images_dir / "image_b.png"),
        "image_c": str(images_dir / "image_c.png"),
    }


if __name__ == "__main__":
    create_test_images()
