import logging
import re
import time
from collections import Counter
from functools import lru_cache
from typing import Any, Dict, List

import requests
from bs4 import BeautifulSoup

from data.s3_client import s3_client


class WebPolicyScraper:
    """Handles all web scraping logic for e-commerce policies"""

    def __init__(self):
        self.session = requests.Session()
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Connection": "keep-alive",
        }
        self.session.headers.update(self.headers)
        self.delay = 2  # Respectful delay between requests

    def _make_request(self, url: str) -> requests.Response:
        """Make a respectful HTTP request with error handling"""
        try:
            time.sleep(self.delay)
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            return response
        except requests.RequestException as e:
            logging.error(f"Error fetching {url}: {e}")
            return None

    def _clean_text(self, text: str) -> str:
        """Clean and normalize scraped text"""
        if not text:
            return ""
        # Remove extra whitespace and normalize
        text = re.sub(r"\s+", " ", text.strip())
        # Remove common unwanted characters
        text = re.sub(r"[^\w\s\.,!?;:()\-]", "", text)
        return text

    def _is_quality_content(self, text: str) -> bool:
        """Check if scraped content meets quality standards"""
        if not text or len(text) < 50:
            return False

        # Filter out common junk content
        junk_indicators = [
            "copyright",
            "©",
            "all rights reserved",
            "privacy policy",
            "terms of service",
            "cookie policy",
            "javascript",
            "enable cookies",
            "browser not supported",
            "error 404",
            "page not found",
        ]

        text_lower = text.lower()
        if any(indicator in text_lower for indicator in junk_indicators):
            return False

        # Must contain some useful keywords for e-commerce
        useful_keywords = [
            "shipping",
            "delivery",
            "return",
            "refund",
            "warranty",
            "policy",
            "customer",
            "service",
            "support",
            "order",
            "product",
            "payment",
        ]

        if not any(keyword in text_lower for keyword in useful_keywords):
            return False

        return True

    def _extract_contextual_content(
        self, soup: BeautifulSoup, selectors: str, keywords: List[str], max_items: int = 3
    ) -> List[str]:
        """Extract contextually relevant content based on keywords"""
        content_texts = []
        elements = soup.select(selectors)

        for element in elements:
            text = self._clean_text(element.get_text())
            if text and self._is_quality_content(text):
                text_lower = text.lower()
                if any(keyword in text_lower for keyword in keywords):
                    content_texts.append(text)
                    if len(content_texts) >= max_items:
                        break

        return content_texts

    def _scrape_return_policies(self) -> List[Dict[str, Any]]:
        """Scrape return policy information from major e-commerce sites"""
        policies = []

        # Working sources for e-commerce policies
        targets = [
            {
                "name": "Better Business Bureau Online Shopping Guidelines",
                "url": "https://www.bbb.org/all/online-shopping/smart-shopping-online",
                "selectors": "p, li, h3 + p, h4 + p",
            },
            {
                "name": "BBB Online Shopping Best Practices",
                "url": "https://www.bbb.org/all/online-shopping/6-things-to-look-for-when-buying-online",
                "selectors": "p, li, h3 + p, h4 + p",
            },
            {
                "name": "HubSpot E-commerce Planning Resources",
                "url": "https://offers.hubspot.com/ecommerce-planning-kit",
                "selectors": "p, li, h2 + p, h3 + p",
            },
        ]

        return_keywords = [
            "return",
            "refund",
            "exchange",
            "policy",
            "purchase",
            "buy",
            "shop",
            "customer",
        ]

        for target in targets:
            try:
                response = self._make_request(target["url"])
                if not response:
                    continue

                soup = BeautifulSoup(response.text, "html.parser")
                policy_texts = self._extract_contextual_content(
                    soup, target["selectors"], return_keywords
                )

                if policy_texts:
                    combined_text = " ".join(policy_texts)[:500]
                    policies.append(
                        {
                            "title": f"Return Policy from {target['name']}",
                            "content": f"Return Policy from {target['name']}: {combined_text}",
                            "type": "return_policy",
                            "category": "returns",
                            "source": f"scraped_{target['name'].lower().replace(' ', '_')}",
                            "url": target["url"],
                        }
                    )
                    logging.info(f"Scraped return policy from {target['name']}")

            except Exception as e:
                logging.error(f"Error scraping {target['name']}: {e}")
                continue

        return policies

    def _scrape_shipping_policies(self) -> List[Dict[str, Any]]:
        """Scrape shipping policy information"""
        shipping_policies = []

        # Working shipping policy sources
        targets = [
            {
                "name": "BBB Shipping Guidelines",
                "url": "https://www.bbb.org/all/online-shopping/smart-shopping-online",
                "selectors": "p, li, h3 + p, h4 + p",
            },
            {
                "name": "HubSpot Product Shipping Info",
                "url": "https://legal.hubspot.com/hubspot-product-and-services-catalog",
                "selectors": "p, li, td",
            },
        ]

        shipping_keywords = [
            "shipping",
            "delivery",
            "ship",
            "freight",
            "dispatch",
            "send",
            "mail",
            "transport",
        ]

        for target in targets:
            try:
                response = self._make_request(target["url"])
                if not response:
                    continue

                soup = BeautifulSoup(response.text, "html.parser")
                shipping_texts = self._extract_contextual_content(
                    soup, target["selectors"], shipping_keywords
                )

                if shipping_texts:
                    combined_text = " ".join(shipping_texts)[:400]
                    shipping_policies.append(
                        {
                            "title": f"Shipping Policy from {target['name']}",
                            "content": f"Shipping Policy from {target['name']}: {combined_text}",
                            "type": "shipping_policy",
                            "category": "shipping",
                            "source": f"scraped_{target['name'].lower().replace(' ', '_')}",
                            "url": target["url"],
                        }
                    )
                    logging.info(f"Scraped shipping policy from {target['name']}")

            except Exception as e:
                logging.error(f"Error scraping shipping from {target['name']}: {e}")
                continue

        return shipping_policies

    def _scrape_warranty_information(self) -> List[Dict[str, Any]]:
        """Scrape warranty information from various sources"""
        warranty_info = []

        # Working warranty information sources
        targets = [
            {
                "name": "BBB Consumer Protection Guidelines",
                "url": "https://www.bbb.org/all/online-shopping/6-things-to-look-for-when-buying-online",
                "selectors": "p, li, h3 + p, h4 + p",
            },
            {
                "name": "HubSpot Service Terms",
                "url": "https://legal.hubspot.com/terms-of-service",
                "selectors": "p, li, td",
            },
        ]

        warranty_keywords = [
            "warranty",
            "guarantee",
            "protection",
            "coverage",
            "defect",
            "repair",
            "replace",
            "quality",
        ]

        for target in targets:
            try:
                response = self._make_request(target["url"])
                if not response:
                    continue

                soup = BeautifulSoup(response.text, "html.parser")
                warranty_texts = self._extract_contextual_content(
                    soup, target["selectors"], warranty_keywords
                )

                if warranty_texts:
                    combined_text = " ".join(warranty_texts)[:400]
                    warranty_info.append(
                        {
                            "title": f"Warranty Information from {target['name']}",
                            "content": f"Warranty Information from {target['name']}: {combined_text}",
                            "type": "warranty_info",
                            "category": "warranty",
                            "source": f"scraped_{target['name'].lower().replace(' ', '_')}",
                            "url": target["url"],
                        }
                    )
                    logging.info(f"Scraped warranty info from {target['name']}")

            except Exception as e:
                logging.error(f"Error scraping warranty from {target['name']}: {e}")
                continue

        return warranty_info

    def _scrape_additional_policies(self) -> List[Dict[str, Any]]:
        """Scrape additional policies from reliable sources"""
        policies = []

        # Additional reliable sources for e-commerce knowledge
        additional_sources = [
            {
                "name": "HubSpot Product Catalog",
                "url": "https://legal.hubspot.com/hubspot-product-and-services-catalog",
                "keywords": ["product", "service", "subscription", "pricing", "feature"],
                "type": "product_info",
                "category": "product",
            },
            {
                "name": "BBB Online Shopping Scams",
                "url": "https://www.bbb.org/all/online-shopping/online-shopping-scams",
                "keywords": ["scam", "fraud", "security", "safe", "protect", "trust"],
                "type": "security_info",
                "category": "security",
            },
            {
                "name": "HubSpot Customer Terms",
                "url": "https://legal.hubspot.com/terms-of-service",
                "keywords": ["terms", "service", "customer", "agreement", "policy"],
                "type": "terms_info",
                "category": "legal",
            },
        ]

        for source in additional_sources:
            try:
                response = self._make_request(source["url"])
                if response:
                    soup = BeautifulSoup(response.text, "html.parser")
                    relevant_texts = self._extract_contextual_content(
                        soup, "p, li, td", source["keywords"], max_items=2
                    )

                    if relevant_texts:
                        combined_text = " ".join(relevant_texts)[:400]
                        policies.append(
                            {
                                "title": source["name"],
                                "content": f'{source["name"]}: {combined_text}',
                                "type": source["type"],
                                "category": source["category"],
                                "source": f'scraped_{source["name"].lower().replace(" ", "_")}',
                                "url": source["url"],
                            }
                        )
                        logging.info(f"{source['name']} scraping successful")

            except Exception as e:
                logging.error(f"{source['name']} scraping failed: {e}")

        return policies

    def scrape_policies(self) -> List[Dict[str, Any]]:
        """Main method to scrape all web policies"""
        all_policies = []

        try:
            # Scrape different types of information
            all_policies.extend(self._scrape_return_policies())
            all_policies.extend(self._scrape_shipping_policies())
            all_policies.extend(self._scrape_warranty_information())
            all_policies.extend(self._scrape_additional_policies())

            # Add web scraping fallbacks if needed
            if len(all_policies) < 5:
                all_policies.extend(self._get_web_fallbacks())

            # Add unique IDs
            for i, policy in enumerate(all_policies):
                policy["scraper_id"] = f"web_scraped_{i+1}"

        except Exception as e:
            logging.error(f"Error in web scraping: {e}")
            return self._get_web_fallbacks()

        return all_policies

    def _get_web_fallbacks(self) -> List[Dict[str, Any]]:
        """Fallback policies if web scraping fails"""
        return [
            {
                "title": "Standard Shipping Policy",
                "content": "Standard shipping typically takes 3-7 business days for most locations. Expedited shipping options are available for faster delivery.",
                "type": "shipping_policy",
                "category": "shipping",
                "source": "web_fallback",
            },
            {
                "title": "Free Shipping Information",
                "content": "Free shipping is often available for orders over a certain amount, typically $25-$50 depending on the retailer.",
                "type": "shipping_policy",
                "category": "shipping",
                "source": "web_fallback",
            },
        ]


class ProductPolicyScraper:
    """Handles product data extraction from S3 for policy information"""

    def __init__(self):
        pass

    def _load_products(self) -> List[Dict[str, Any]]:
        """Load products from S3 cloud storage"""
        try:
            return s3_client.load_products()
        except Exception as e:
            logging.error(f"Error loading products from S3: {e}")
            return []

    def extract_policies(self) -> List[Dict[str, Any]]:
        """Extract support policies from product data"""
        products = self._load_products()
        if not products:
            return []

        support_docs = []

        # Extract and count different policy types
        return_policies = Counter()
        warranty_info = Counter()
        shipping_info = Counter()

        for product in products:
            # Count return policies
            return_policy = product.get("returnPolicy", "").strip()
            if return_policy and return_policy != "No return policy":
                return_policies[return_policy] += 1

            # Count warranty information
            warranty = product.get("warrantyInformation", "").strip()
            if warranty:
                warranty_info[warranty] += 1

            # Count shipping information
            shipping = product.get("shippingInformation", "").strip()
            if shipping:
                shipping_info[shipping] += 1

        # Create return policy documents
        for policy, count in return_policies.items():
            support_docs.append(
                {
                    "title": "Product Return Policy",
                    "content": f"Return Policy: {policy}. This policy applies to {count} products in our catalog. Customers can return items following this policy.",
                    "type": "return_policy",
                    "category": "returns",
                    "policy": policy,
                    "product_count": count,
                    "source": "product_data",
                }
            )

        # Create warranty documents
        for warranty, count in warranty_info.items():
            support_docs.append(
                {
                    "title": "Product Warranty Information",
                    "content": f"Warranty Information: {warranty}. This warranty coverage applies to {count} products. We honor all manufacturer warranties.",
                    "type": "warranty",
                    "category": "warranty",
                    "warranty": warranty,
                    "product_count": count,
                    "source": "product_data",
                }
            )

        # Create shipping documents
        for shipping, count in shipping_info.items():
            support_docs.append(
                {
                    "title": "Product Shipping Information",
                    "content": f"Shipping Information: {shipping}. This shipping option applies to {count} products in our inventory.",
                    "type": "shipping",
                    "category": "shipping",
                    "shipping": shipping,
                    "product_count": count,
                    "source": "product_data",
                }
            )

        # Add general support documents
        support_docs.extend(
            [
                {
                    "title": "General Return Policy",
                    "content": "We accept returns for most items. Return policies vary by product type and can range from 7 days to 90 days. Please check the specific return policy for your item.",
                    "type": "general_return",
                    "category": "returns",
                    "source": "general_policy",
                },
                {
                    "title": "Defective Items Support",
                    "content": "For defective items, please contact our customer service team. We will arrange for a replacement or refund based on the product warranty terms.",
                    "type": "defective_items",
                    "category": "support",
                    "source": "general_policy",
                },
                {
                    "title": "General Shipping Information",
                    "content": "Shipping times vary by product and location. Most items ship within 1-3 business days. Express and overnight shipping options are available for many products.",
                    "type": "general_shipping",
                    "category": "shipping",
                    "source": "general_policy",
                },
            ]
        )

        # Add unique IDs
        for i, doc in enumerate(support_docs):
            doc["product_id"] = f"product_policy_{i+1}"

        return support_docs

    def get_policy_summary(self) -> Dict[str, Any]:
        """Get a summary of product policies"""
        products = self._load_products()

        if not products:
            return {
                "total_products": 0,
                "unique_return_policies": 0,
                "unique_warranties": 0,
                "unique_shipping_options": 0,
                "return_policy_examples": [],
                "warranty_examples": [],
                "shipping_examples": [],
            }

        return_policies = [p.get("returnPolicy", "") for p in products if p.get("returnPolicy")]
        warranties = [
            p.get("warrantyInformation", "") for p in products if p.get("warrantyInformation")
        ]
        shipping = [
            p.get("shippingInformation", "") for p in products if p.get("shippingInformation")
        ]

        return {
            "total_products": len(products),
            "unique_return_policies": len(set(return_policies)),
            "unique_warranties": len(set(warranties)),
            "unique_shipping_options": len(set(shipping)),
            "return_policy_examples": list(set(return_policies))[:5],
            "warranty_examples": list(set(warranties))[:5],
            "shipping_examples": list(set(shipping))[:5],
        }


class KnowledgeProvider:
    """Main orchestrator for all knowledge sources"""

    def __init__(self):
        self.web_scraper = WebPolicyScraper()
        self.product_scraper = ProductPolicyScraper()

    def get_general_ecommerce_faqs(self) -> List[Dict[str, Any]]:
        """Get comprehensive static e-commerce FAQ knowledge base"""
        faqs = [
            {
                "title": "Return Policy Guidelines",
                "content": "Return Policy: Most e-commerce stores offer 15-30 day return windows. Items must be in original condition with tags attached. Some restrictions apply to electronics and personal items.",
                "type": "return_policy",
                "category": "returns",
                "source": "ecommerce_standard",
            },
            {
                "title": "Shipping Information",
                "content": "Shipping Information: Standard shipping typically takes 3-7 business days. Express shipping (1-2 days) and overnight shipping are often available for additional cost.",
                "type": "shipping_policy",
                "category": "shipping",
                "source": "ecommerce_standard",
            },
            {
                "title": "Warranty Coverage",
                "content": "Warranty Coverage: Products come with manufacturer warranties. Extended warranties may be available for electronics. Warranty terms vary by brand and product type.",
                "type": "warranty_policy",
                "category": "warranty",
                "source": "ecommerce_standard",
            },
            {
                "title": "Defective Items Policy",
                "content": "Defective Items: If you receive a defective item, contact customer service within 48 hours. We will arrange for return or exchange at no cost to you.",
                "type": "defective_items",
                "category": "support",
                "source": "ecommerce_standard",
            },
            {
                "title": "Order Tracking",
                "content": "Order Tracking: You will receive tracking information via email once your order ships. Track your package using the provided tracking number.",
                "type": "order_tracking",
                "category": "shipping",
                "source": "ecommerce_standard",
            },
            {
                "title": "Customer Service",
                "content": "Customer Service: Our customer service team is available to help with orders, returns, and product questions. Contact us for assistance with any issues.",
                "type": "customer_service",
                "category": "support",
                "source": "ecommerce_standard",
            },
            {
                "title": "Payment Options",
                "content": "Payment Options: We accept major credit cards, PayPal, and other secure payment methods. Your payment information is protected with industry-standard encryption.",
                "type": "payment_info",
                "category": "payment",
                "source": "ecommerce_standard",
            },
            {
                "title": "Account Management",
                "content": "Account Management: Create an account to track orders, manage returns, and save your shipping information for faster checkout.",
                "type": "account_info",
                "category": "account",
                "source": "ecommerce_standard",
            },
            {
                "title": "Product Information",
                "content": "Product Information: Product descriptions, specifications, and images are provided to help you make informed purchasing decisions. Contact us if you need additional product details.",
                "type": "product_info",
                "category": "products",
                "source": "ecommerce_standard",
            },
            {
                "title": "Privacy Policy",
                "content": "Privacy Policy: We protect your personal information and do not share it with third parties without your consent. See our privacy policy for complete details.",
                "type": "privacy_info",
                "category": "privacy",
                "source": "ecommerce_standard",
            },
        ]

        return faqs

    def get_category_specific_faqs(self) -> List[Dict[str, Any]]:
        """Get category-specific FAQ knowledge"""
        category_faqs = [
            {
                "title": "Electronics Return Policy",
                "content": "Electronics Return Policy: Electronics can typically be returned within 15-30 days if unopened. Opened electronics may have a shorter return window. Software and digital downloads are often non-returnable.",
                "type": "electronics_returns",
                "category": "returns",
                "source": "category_specific",
            },
            {
                "title": "Electronics Warranty",
                "content": "Electronics Warranty: Electronics come with manufacturer warranties ranging from 90 days to 3 years. Extended warranties are available for purchase on most electronic items.",
                "type": "electronics_warranty",
                "category": "warranty",
                "source": "category_specific",
            },
            {
                "title": "Clothing Returns",
                "content": "Clothing Returns: Clothing items can usually be returned within 30-60 days with tags attached. Items must be unworn and in original condition.",
                "type": "clothing_returns",
                "category": "returns",
                "source": "category_specific",
            },
            {
                "title": "Home & Garden Shipping",
                "content": "Home & Garden Shipping: Large furniture and appliances may require special delivery arrangements. Assembly services may be available for an additional fee.",
                "type": "home_garden_shipping",
                "category": "shipping",
                "source": "category_specific",
            },
            {
                "title": "Beauty Products",
                "content": "Beauty Products: Beauty and personal care items are typically non-returnable for hygiene reasons unless they arrive damaged or defective.",
                "type": "beauty_returns",
                "category": "returns",
                "source": "category_specific",
            },
        ]

        return category_faqs

    def _deduplicate_and_enrich(
        self, knowledge_items: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Remove duplicates and enrich knowledge items with consistent structure"""
        # Simple deduplication by content similarity
        seen_content = set()
        unique_items = []

        for item in knowledge_items:
            content_key = item.get("content", "")[:100].lower()  # First 100 chars for comparison
            if content_key not in seen_content:
                seen_content.add(content_key)

                # Ensure consistent structure
                if "title" not in item and "type" in item:
                    item["title"] = item["type"].replace("_", " ").title()

                unique_items.append(item)

        return unique_items

    @lru_cache(maxsize=1)
    def get_all_knowledge(self) -> List[Dict[str, Any]]:
        """Get all knowledge from all sources - cached for performance"""
        all_knowledge = []

        # Always start with reliable static knowledge
        all_knowledge.extend(self.get_general_ecommerce_faqs())
        all_knowledge.extend(self.get_category_specific_faqs())
        logging.info(f"Loaded {len(all_knowledge)} static knowledge items")

        # Try to get web scraped policies
        try:
            web_policies = self.web_scraper.scrape_policies()
            all_knowledge.extend(web_policies)
            logging.info(f"Added {len(web_policies)} web scraped policies")
        except Exception as e:
            logging.warning(f"Web scraping failed: {e}")

        # Try to get product policies
        try:
            product_policies = self.product_scraper.extract_policies()
            all_knowledge.extend(product_policies)
            logging.info(f"Added {len(product_policies)} product policies")
        except Exception as e:
            logging.warning(f"Product policy extraction failed: {e}")

        # Deduplicate and enrich
        all_knowledge = self._deduplicate_and_enrich(all_knowledge)

        # Add final unique IDs for any items without them
        for i, item in enumerate(all_knowledge):
            if "faq_id" not in item and "scraper_id" not in item and "product_id" not in item:
                item["faq_id"] = f"knowledge_{i+1}"

        logging.info(f"Total knowledge items: {len(all_knowledge)}")
        return all_knowledge

    def get_knowledge_summary(self) -> Dict[str, Any]:
        """Get comprehensive summary of all knowledge sources"""
        knowledge = self.get_all_knowledge()

        # Count by source
        source_counts = {}
        category_counts = {}
        type_counts = {}

        for item in knowledge:
            source = item.get("source", "unknown")
            category = item.get("category", "unknown")
            type_name = item.get("type", "unknown")

            source_counts[source] = source_counts.get(source, 0) + 1
            category_counts[category] = category_counts.get(category, 0) + 1
            type_counts[type_name] = type_counts.get(type_name, 0) + 1

        # Get product summary if available
        product_summary = {}
        try:
            product_summary = self.product_scraper.get_policy_summary()
        except Exception as e:
            logging.warning(f"Could not get product summary: {e}")

        return {
            "total_knowledge_items": len(knowledge),
            "source_breakdown": source_counts,
            "category_breakdown": category_counts,
            "type_breakdown": type_counts,
            "product_summary": product_summary,
            "has_web_scraped_content": any(
                "scraped_" in item.get("source", "") for item in knowledge
            ),
            "has_product_content": any("product_" in item.get("source", "") for item in knowledge),
        }
