import argparse
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright


async def html_to_single_page_pdf(html_path: str, output_pdf: str, width_mm: float = 210, height_mm: float = None):
    html_file = Path(html_path).resolve().as_uri()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        viewport_width_px = round(width_mm / 25.4 * 96)
        await page.set_viewport_size({"width": viewport_width_px, "height": 600})

        await page.goto(html_file, wait_until="networkidle")

        # Wait for images to be fully loaded
        await page.wait_for_function(
            """() => {
                const images = Array.from(document.images);
                return images.every(img => img.complete && img.naturalHeight !== 0);
            }""",
            timeout=30000,
        )

        # Hide elements that are not needed in a single-page PDF
        await page.add_style_tag(
            content="""
                .navbar,
                .quarto-secondary-nav,
                #quarto-back-to-top,
                .page-navigation,
                footer,
                .nav-footer {
                    display: none !important;
                }
                body {
                    margin: 0 !important;
                    padding: 0 !important;
                    overflow: hidden !important;
                }
                main {
                    max-width: 100% !important;
                    padding: 20px !important;
                    box-sizing: border-box !important;
                }
            """
        )

        # Wait long enough for layout reflow after hiding elements
        await asyncio.sleep(1.5)

        if height_mm is not None:
            page_height_px = height_mm / 25.4 * 96
        else:
            page_height_px = await page.evaluate("""
                () => {
                    const appendix = document.getElementById('quarto-appendix');
                    if (appendix && appendix.previousElementSibling) {
                        return appendix.previousElementSibling.getBoundingClientRect().bottom + 20;
                    }
                    const main = document.querySelector('main');
                    return main ? main.getBoundingClientRect().bottom : document.body.scrollHeight;
                }
            """)

        # Convert width from mm to inches (1 inch = 25.4 mm)
        width_inch = width_mm / 25.4
        # Keep pixel density at 96 DPI for 1:1 mapping
        height_inch = page_height_px / 96

        await page.pdf(
            path=output_pdf,
            width=f"{width_inch}in",
            height=f"{height_inch}in",
            print_background=True,
            margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
        )

        await browser.close()

    if height_mm is not None:
        print(f"PDF saved to: {output_pdf}")
        print(f"Page dimensions: {width_mm}mm x {height_mm:.1f}mm (manual)")
    else:
        print(f"PDF saved to: {output_pdf}")
        print(f"Page dimensions: {width_mm}mm x {page_height_px / 96 * 25.4:.1f}mm (auto)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert HTML to single-page PDF")
    parser.add_argument("html", help="Path to input HTML file")
    parser.add_argument("-o", "--output", help="Path to output PDF file")
    parser.add_argument(
        "--width", type=float, default=210, help="Page width in mm (default: 210)"
    )
    parser.add_argument(
        "--height", type=float, default=None,
        help="Page height in mm. If not set, auto-detect from content"
    )
    args = parser.parse_args()

    html_path = Path(args.html)
    if args.output:
        output_pdf = Path(args.output)
    else:
        output_pdf = html_path.with_suffix(".pdf")

    asyncio.run(html_to_single_page_pdf(str(html_path), str(output_pdf), args.width, args.height))
