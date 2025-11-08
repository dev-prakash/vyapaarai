"""
Rich Card Templates for RCS Business Messaging
Provides templates for various message types in VyaparAI
"""

from typing import List, Dict, Optional, Any
from datetime import datetime
import json

class OrderConfirmationCard:
    """Rich card for order confirmation"""
    
    def __init__(self, order_id: str, items: List[Dict], total: float, language: str = 'en'):
        self.order_id = order_id
        self.items = items
        self.total = total
        self.language = language
    
    def build(self) -> Dict[str, Any]:
        """Build rich card JSON"""
        
        # Format items list
        items_text = self._format_items()
        
        return {
            "title": self._get_title(),
            "description": f"{self._get_description()}\n\n{items_text}",
            "media": {
                "height": "MEDIUM",
                "contentInfo": {
                    "fileUrl": "https://vyaparai.com/images/order-confirmed.png",
                    "forceRefresh": False
                }
            },
            "suggestions": [
                {
                    "reply": {
                        "text": "✅ Confirm",
                        "postbackData": f"action=confirm_order&order_id={self.order_id}"
                    }
                },
                {
                    "reply": {
                        "text": "❌ Cancel",
                        "postbackData": f"action=cancel_order&order_id={self.order_id}"
                    }
                },
                {
                    "action": {
                        "text": "📍 Track Order",
                        "postbackData": f"action=track&order_id={self.order_id}",
                        "openUrlAction": {
                            "url": f"https://vyaparai.com/track/{self.order_id}"
                        }
                    }
                }
            ]
        }
    
    def _format_items(self) -> str:
        """Format items list for display"""
        if not self.items:
            return "No items specified"
        
        items_list = []
        for item in self.items:
            product = item.get('product', 'Unknown')
            quantity = item.get('quantity', 0)
            unit = item.get('unit', '')
            brand = item.get('brand', '')
            
            item_text = f"• {quantity} {unit} {product}"
            if brand:
                item_text += f" ({brand})"
            
            items_list.append(item_text)
        
        return "\n".join(items_list)
    
    def _get_title(self) -> str:
        """Get localized title"""
        titles = {
            'en': f"Order #{self.order_id}",
            'hi': f"ऑर्डर #{self.order_id}",
            'ta': f"ஆர்டர் #{self.order_id}",
            'bn': f"অর্ডার #{self.order_id}",
            'te': f"ఆర్డర్ #{self.order_id}",
            'mr': f"ऑर्डर #{self.order_id}",
            'gu': f"ઓર્ડર #{self.order_id}",
            'kn': f"ಆರ್ಡರ್ #{self.order_id}",
            'ml': f"ഓർഡർ #{self.order_id}",
            'pa': f"ਆਰਡਰ #{self.order_id}"
        }
        return titles.get(self.language, titles['en'])
    
    def _get_description(self) -> str:
        """Get localized description"""
        descriptions = {
            'en': f"Total: ₹{self.total}\nDelivery: 30-45 minutes",
            'hi': f"कुल: ₹{self.total}\nडिलीवरी: 30-45 मिनट",
            'ta': f"மொத்தம்: ₹{self.total}\nடெலிவரி: 30-45 நிமிடங்கள்",
            'bn': f"মোট: ₹{self.total}\nডেলিভারি: 30-45 মিনিট",
            'te': f"మొత్తం: ₹{self.total}\nడెలివరీ: 30-45 నిమిషాలు",
            'mr': f"एकूण: ₹{self.total}\nडिलिव्हरी: 30-45 मिनिटे",
            'gu': f"કુલ: ₹{self.total}\nડિલિવરી: 30-45 મિનિટ",
            'kn': f"ಒಟ್ಟು: ₹{self.total}\nಡೆಲಿವರಿ: 30-45 ನಿಮಿಷಗಳು",
            'ml': f"ആകെ: ₹{self.total}\nഡെലിവറി: 30-45 മിനിറ്റ്",
            'pa': f"ਕੁੱਲ: ₹{self.total}\nਡਿਲਿਵਰੀ: 30-45 ਮਿੰਟ"
        }
        return descriptions.get(self.language, descriptions['en'])

class ProductCarousel:
    """Carousel of product cards"""
    
    def __init__(self, products: List[Dict], language: str = 'en'):
        self.products = products[:10]  # Max 10 cards
        self.language = language
    
    def build(self) -> List[Dict[str, Any]]:
        """Build carousel cards"""
        
        cards = []
        for product in self.products:
            # Extract product details
            product_name = self._get_product_name(product)
            price = product.get('price', 0)
            unit = product.get('unit', 'piece')
            brand = product.get('brand', '')
            stock = product.get('stock_quantity', 0)
            
            # Build description
            description = f"₹{price} per {unit}"
            if brand:
                description += f" • {brand}"
            if stock > 0:
                description += f" • In stock: {stock}"
            else:
                description += " • Out of stock"
            
            card = {
                "title": product_name,
                "description": description,
                "media": {
                    "height": "MEDIUM",
                    "contentInfo": {
                        "fileUrl": self._get_product_image(product),
                        "forceRefresh": False
                    }
                },
                "suggestions": self._get_product_suggestions(product)
            }
            
            cards.append(card)
        
        return cards
    
    def _get_product_name(self, product: Dict) -> str:
        """Get localized product name"""
        name = product.get('name', 'Product')
        
        # If name is a JSON object with language keys
        if isinstance(name, dict):
            return name.get(self.language, name.get('en', 'Product'))
        
        return name
    
    def _get_product_image(self, product: Dict) -> str:
        """Get product image URL"""
        product_id = product.get('product_id', product.get('id', 'default'))
        return f"https://vyaparai.com/products/{product_id}.jpg"
    
    def _get_product_suggestions(self, product: Dict) -> List[Dict[str, Any]]:
        """Get product-specific suggestions"""
        product_id = product.get('product_id', product.get('id', ''))
        
        return [
            {
                "reply": {
                    "text": "Order 1",
                    "postbackData": f"action=order&product={product_id}&qty=1"
                }
            },
            {
                "reply": {
                    "text": "Order 2",
                    "postbackData": f"action=order&product={product_id}&qty=2"
                }
            },
            {
                "reply": {
                    "text": "Add to Cart",
                    "postbackData": f"action=add_to_cart&product={product_id}"
                }
            }
        ]

class OrderStatusCard:
    """Rich card for order status"""
    
    def __init__(self, order_id: str, status: str, language: str = 'en', order_details: Optional[Dict] = None):
        self.order_id = order_id
        self.status = status
        self.language = language
        self.order_details = order_details or {}
    
    def build(self) -> Dict[str, Any]:
        """Build order status card"""
        
        return {
            "title": self._get_title(),
            "description": self._get_description(),
            "media": {
                "height": "MEDIUM",
                "contentInfo": {
                    "fileUrl": self._get_status_image(),
                    "forceRefresh": False
                }
            },
            "suggestions": self._get_status_suggestions()
        }
    
    def _get_title(self) -> str:
        """Get localized title"""
        titles = {
            'en': f"Order #{self.order_id} Status",
            'hi': f"ऑर्डर #{self.order_id} स्थिति",
            'ta': f"ஆர்டர் #{self.order_id} நிலை",
            'bn': f"অর্ডার #{self.order_id} স্থিতি",
            'te': f"ఆర్డర్ #{self.order_id} స్థితి",
            'mr': f"ऑर्डर #{self.order_id} स्थिती",
            'gu': f"ઓર્ડર #{self.order_id} સ્થિતિ",
            'kn': f"ಆರ್ಡರ್ #{self.order_id} ಸ್ಥಿತಿ",
            'ml': f"ഓർഡർ #{self.order_id} നില",
            'pa': f"ਆਰਡਰ #{self.order_id} ਸਥਿਤੀ"
        }
        return titles.get(self.language, titles['en'])
    
    def _get_description(self) -> str:
        """Get localized description with status"""
        status_text = self._get_status_text()
        
        # Add order details if available
        details = ""
        if self.order_details:
            total = self.order_details.get('total_amount', 0)
            created_at = self.order_details.get('created_at', '')
            
            if total:
                details += f"\nTotal: ₹{total}"
            if created_at:
                details += f"\nOrdered: {created_at}"
        
        return f"{status_text}{details}"
    
    def _get_status_text(self) -> str:
        """Get localized status text"""
        status_map = {
            'pending': {
                'en': "⏳ Your order is being processed",
                'hi': "⏳ आपका ऑर्डर प्रोसेस हो रहा है",
                'ta': "⏳ உங்கள் ஆர்டர் செயலாக்கப்படுகிறது",
                'bn': "⏳ আপনার অর্ডার প্রক্রিয়াকরণ হচ্ছে",
                'te': "⏳ మీ ఆర్డర్ ప్రాసెస్ చేయబడుతోంది",
                'mr': "⏳ तुमचा ऑर्डर प्रक्रिया करत आहे",
                'gu': "⏳ તમારો ઓર્ડર પ્રક્રિયા કરી રહ્યા છીએ",
                'kn': "⏳ ನಿಮ್ಮ ಆರ್ಡರ್ ಪ್ರಕ್ರಿಯೆಗೊಳಗಾಗುತ್ತಿದೆ",
                'ml': "⏳ നിങ്ങളുടെ ഓർഡർ പ്രോസസ്സ് ചെയ്യുന്നു",
                'pa': "⏳ ਤੁਹਾਡਾ ਆਰਡਰ ਪ੍ਰਕਿਰਿਆ ਕਰ ਰਿਹਾ ਹੈ"
            },
            'confirmed': {
                'en': "✅ Order confirmed! Preparing for delivery",
                'hi': "✅ ऑर्डर कन्फर्म! डिलीवरी के लिए तैयार",
                'ta': "✅ ஆர்டர் உறுதி! டெலிவரிக்கு தயாராகிறது",
                'bn': "✅ অর্ডার নিশ্চিত! ডেলিভারির জন্য প্রস্তুত",
                'te': "✅ ఆర్డర్ నిర్ధారించబడింది! డెలివరీకి సిద్ధం",
                'mr': "✅ ऑर्डर कन्फर्म! डिलिव्हरीसाठी तयार",
                'gu': "✅ ઓર્ડર કન્ફર્મ! ડિલિવરી માટે તૈયાર",
                'kn': "✅ ಆರ್ಡರ್ ದೃಢೀಕರಿಸಲಾಗಿದೆ! ಡೆಲಿವರಿಗಾಗಿ ಸಿದ್ಧ",
                'ml': "✅ ഓർഡർ സ്ഥിരീകരിച്ചു! ഡെലിവറിക്ക് തയ്യാറാക്കുന്നു",
                'pa': "✅ ਆਰਡਰ ਦੀ ਪੁਸ਼ਟੀ! ਡਿਲਿਵਰੀ ਲਈ ਤਿਆਰ"
            },
            'preparing': {
                'en': "👨‍🍳 Your order is being prepared",
                'hi': "👨‍🍳 आपका ऑर्डर तैयार किया जा रहा है",
                'ta': "👨‍🍳 உங்கள் ஆர்டர் தயாரிக்கப்படுகிறது",
                'bn': "👨‍🍳 আপনার অর্ডার প্রস্তুত করা হচ্ছে",
                'te': "👨‍🍳 మీ ఆర్డర్ తయారు చేయబడుతోంది",
                'mr': "👨‍🍳 तुमचा ऑर्डर तयार करत आहे",
                'gu': "👨‍🍳 તમારો ઓર્ડર તૈયાર કરી રહ્યા છીએ",
                'kn': "👨‍🍳 ನಿಮ್ಮ ಆರ್ಡರ್ ತಯಾರಿಸಲಾಗುತ್ತಿದೆ",
                'ml': "👨‍🍳 നിങ്ങളുടെ ഓർഡർ തയ്യാറാക്കുന്നു",
                'pa': "👨‍🍳 ਤੁਹਾਡਾ ਆਰਡਰ ਤਿਆਰ ਕੀਤਾ ਜਾ ਰਿਹਾ ਹੈ"
            },
            'out_for_delivery': {
                'en': "🚚 Your order is out for delivery",
                'hi': "🚚 आपका ऑर्डर डिलीवरी के लिए निकल गया है",
                'ta': "🚚 உங்கள் ஆர்டர் டெலிவரிக்கு வெளியே சென்றுள்ளது",
                'bn': "🚚 আপনার অর্ডার ডেলিভারির জন্য বের হয়েছে",
                'te': "🚚 మీ ఆర్డర్ డెలివరీకి బయటకు వెళ్లింది",
                'mr': "🚚 तुमचा ऑर्डर डिलिव्हरीसाठी बाहेर गेला आहे",
                'gu': "🚚 તમારો ઓર્ડર ડિલિવરી માટે બહાર ગયો છે",
                'kn': "🚚 ನಿಮ್ಮ ಆರ್ಡರ್ ಡೆಲಿವರಿಗಾಗಿ ಹೊರಟಿದೆ",
                'ml': "🚚 നിങ്ങളുടെ ഓർഡർ ഡെലിവറിക്ക് പുറത്താണ്",
                'pa': "🚚 ਤੁਹਾਡਾ ਆਰਡਰ ਡਿਲਿਵਰੀ ਲਈ ਬਾਹਰ ਗਿਆ ਹੈ"
            },
            'delivered': {
                'en': "🎉 Order delivered successfully!",
                'hi': "🎉 ऑर्डर सफलतापूर्वक डिलीवर हो गया!",
                'ta': "🎉 ஆர்டர் வெற்றிகரமாக டெலிவர் செய்யப்பட்டது!",
                'bn': "🎉 অর্ডার সফলভাবে ডেলিভারি হয়েছে!",
                'te': "🎉 ఆర్డర్ విజయవంతంగా డెలివర్ చేయబడింది!",
                'mr': "🎉 ऑर्डर यशस्वीरित्या डिलिव्हर झाले!",
                'gu': "🎉 ઓર્ડર સફળતાપૂર્વક ડિલિવર થયો!",
                'kn': "🎉 ಆರ್ಡರ್ ಯಶಸ್ವಿಯಾಗಿ ಡೆಲಿವರ್ ಆಗಿದೆ!",
                'ml': "🎉 ഓർഡർ വിജയകരമായി ഡെലിവർ ചെയ്തു!",
                'pa': "🎉 ਆਰਡਰ ਸਫਲਤਾਪੂਰਵਕ ਡਿਲਿਵਰ ਕੀਤਾ ਗਿਆ!"
            },
            'cancelled': {
                'en': "❌ Order has been cancelled",
                'hi': "❌ ऑर्डर रद्द कर दिया गया है",
                'ta': "❌ ஆர்டர் ரத்து செய்யப்பட்டுள்ளது",
                'bn': "❌ অর্ডার বাতিল করা হয়েছে",
                'te': "❌ ఆర్డర్ రద్దు చేయబడింది",
                'mr': "❌ ऑर्डर रद्द केले आहे",
                'gu': "❌ ઓર્ડર રદ કરવામાં આવ્યો છે",
                'kn': "❌ ಆರ್ಡರ್ ರದ್ದುಗೊಳಿಸಲಾಗಿದೆ",
                'ml': "❌ ഓർഡർ റദ്ദാക്കി",
                'pa': "❌ ਆਰਡਰ ਰੱਦ ਕਰ ਦਿੱਤਾ ਗਿਆ ਹੈ"
            }
        }
        
        status_texts = status_map.get(self.status, status_map['pending'])
        return status_texts.get(self.language, status_texts['en'])
    
    def _get_status_image(self) -> str:
        """Get status-specific image URL"""
        status_images = {
            'pending': 'https://vyaparai.com/images/status-pending.png',
            'confirmed': 'https://vyaparai.com/images/status-confirmed.png',
            'preparing': 'https://vyaparai.com/images/status-preparing.png',
            'out_for_delivery': 'https://vyaparai.com/images/status-delivery.png',
            'delivered': 'https://vyaparai.com/images/status-delivered.png',
            'cancelled': 'https://vyaparai.com/images/status-cancelled.png'
        }
        return status_images.get(self.status, status_images['pending'])
    
    def _get_status_suggestions(self) -> List[Dict[str, Any]]:
        """Get status-specific suggestions"""
        if self.status == 'delivered':
            return [
                {
                    "reply": {
                        "text": "🛒 Order Again",
                        "postbackData": "action=place_order"
                    }
                },
                {
                    "reply": {
                        "text": "⭐ Rate Order",
                        "postbackData": f"action=rate_order&order_id={self.order_id}"
                    }
                },
                {
                    "reply": {
                        "text": "📞 Contact Support",
                        "postbackData": "action=support"
                    }
                }
            ]
        elif self.status == 'cancelled':
            return [
                {
                    "reply": {
                        "text": "🛒 Place New Order",
                        "postbackData": "action=place_order"
                    }
                },
                {
                    "reply": {
                        "text": "📞 Contact Support",
                        "postbackData": "action=support"
                    }
                }
            ]
        else:
            return [
                {
                    "reply": {
                        "text": "📍 Track Order",
                        "postbackData": f"action=track_order&order_id={self.order_id}"
                    }
                },
                {
                    "reply": {
                        "text": "📞 Contact Support",
                        "postbackData": "action=support"
                    }
                },
                {
                    "action": {
                        "text": "🌐 View on Web",
                        "postbackData": f"action=view_web&order_id={self.order_id}",
                        "openUrlAction": {
                            "url": f"https://vyaparai.com/orders/{self.order_id}"
                        }
                    }
                }
            ]

class WelcomeCard:
    """Welcome card for new users"""
    
    def __init__(self, language: str = 'en', user_name: str = None):
        self.language = language
        self.user_name = user_name
    
    def build(self) -> Dict[str, Any]:
        """Build welcome card"""
        
        return {
            "title": self._get_title(),
            "description": self._get_description(),
            "media": {
                "height": "MEDIUM",
                "contentInfo": {
                    "fileUrl": "https://vyaparai.com/images/welcome-banner.png",
                    "forceRefresh": False
                }
            },
            "suggestions": [
                {
                    "reply": {
                        "text": "🛒 Start Shopping",
                        "postbackData": "action=place_order"
                    }
                },
                {
                    "reply": {
                        "text": "📋 View Menu",
                        "postbackData": "action=browse"
                    }
                },
                {
                    "reply": {
                        "text": "📍 Find Store",
                        "postbackData": "action=find_store"
                    }
                },
                {
                    "action": {
                        "text": "🌐 Visit Website",
                        "postbackData": "action=visit_website",
                        "openUrlAction": {
                            "url": "https://vyaparai.com"
                        }
                    }
                }
            ]
        }
    
    def _get_title(self) -> str:
        """Get localized welcome title"""
        if self.user_name:
            titles = {
                'en': f"Welcome, {self.user_name}! 👋",
                'hi': f"स्वागत है, {self.user_name}! 👋",
                'ta': f"வரவேற்கிறோம், {self.user_name}! 👋",
                'bn': f"স্বাগতম, {self.user_name}! 👋",
                'te': f"స్వాగతం, {self.user_name}! 👋",
                'mr': f"स्वागत आहे, {self.user_name}! 👋",
                'gu': f"સ્વાગત છે, {self.user_name}! 👋",
                'kn': f"ಸುಸ್ವಾಗತ, {self.user_name}! 👋",
                'ml': f"സ്വാഗതം, {self.user_name}! 👋",
                'pa': f"ਸਵਾਗਤ ਹੈ, {self.user_name}! 👋"
            }
        else:
            titles = {
                'en': "Welcome to VyaparAI! 👋",
                'hi': "VyaparAI में आपका स्वागत है! 👋",
                'ta': "VyaparAI க்கு வரவேற்கிறோம்! 👋",
                'bn': "VyaparAI தே ஸ்வா஗தம்! 👋",
                'te': "VyaparAI கி ஸ்வா஗தம்! 👋",
                'mr': "VyaparAI மதியில் ஸ்வா஗த ஆகிறது! 👋",
                'gu': "VyaparAI மாலை ஸ்வா஗த ஆகிறது! 👋",
                'kn': "VyaparAI கு ஸுஸ்வா஗த! 👋",
                'ml': "VyaparAI லேக்கு ஸ்வா஗தம்! 👋",
                'pa': "VyaparAI வினையில் ஸਵா஗த ஆகிறது! 👋"
            }
        
        return titles.get(self.language, titles['en'])
    
    def _get_description(self) -> str:
        """Get localized welcome description"""
        descriptions = {
            'en': "Order groceries in any language. Fast delivery in 30-45 minutes! 🚚",
            'hi': "किसी भी भाषा में किराने का सामान ऑर्डर करें। 30-45 मिनट में तेज डिलीवरी! 🚚",
            'ta': "எந்த மொழியிலும் கடை பொருட்களை ஆர்டர் செய்யுங்கள். 30-45 நிமிடங்களில் வேக டெலிவரி! 🚚",
            'bn': "যেকোনো ভাষায় মুদি সামগ্রী অর্ডার করুন। 30-45 মিনিটে দ্রুত ডেলিভারি! 🚚",
            'te': "ఏ భాషలోనైనా కిరాణా వస్తువులు ఆర్డర్ చేయండి. 30-45 నిమిషాల్లో వేగవంతమైన డెలివరీ! 🚚",
            'mr': "कोणत्याही भाषेत किराणा माल ऑर्डर करा. 30-45 मिनिटांत वेगवान डिलिव्हरी! 🚚",
            'gu': "કોઈપણ ભાષામાં કિરાણા માલ ઓર્ડર કરો. 30-45 મિનિટમાં ઝડપી ડિલિવરી! 🚚",
            'kn': "ಯಾವುದೇ ಭಾಷೆಯಲ್ಲಿ ಕಿರಾಣಾ ಸರಕುಗಳನ್ನು ಆರ್ಡರ್ ಮಾಡಿ. 30-45 ನಿಮಿಷಗಳಲ್ಲಿ ವೇಗದ ಡೆಲಿವರಿ! 🚚",
            'ml': "ഏത് ഭാഷയിലും കിരാണ സാധനങ്ങൾ ഓർഡർ ചെയ്യുക. 30-45 മിനിറ്റിനുള്ളിൽ വേഗ ഡെലിവറി! 🚚",
            'pa': "ਕਿਸੇ ਵੀ ਭਾਸ਼ਾ ਵਿੱਚ ਕਿਰਾਣਾ ਸਮਾਨ ਆਰਡਰ ਕਰੋ। 30-45 ਮਿੰਟਾਂ ਵਿੱਚ ਤੇਜ਼ ਡਿਲਿਵਰੀ! 🚚"
        }
        return descriptions.get(self.language, descriptions['en'])
