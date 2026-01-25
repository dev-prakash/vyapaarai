#!/usr/bin/env python3
"""
Populate stores with rich content (About, Story, Values, Trust, Media)
"""
import boto3
import json
from datetime import datetime

# Initialize DynamoDB
dynamodb = boto3.resource('dynamodb', region_name='ap-south-1')
stores_table = dynamodb.Table('vyaparai-stores-prod')

def populate_morning_star():
    """Morning Star Bakery and General Store"""
    store_id = "STORE-01K5SBCNYJP5V4ZCP3EVYKH4KV"

    content = {
        "media": {
            "images": [
                {
                    "url": "https://images.unsplash.com/photo-1509440159596-0249088772ff",
                    "caption": "Fresh artisan bread baked daily",
                    "order": 1,
                    "is_primary": True
                },
                {
                    "url": "https://images.unsplash.com/photo-1555507036-ab1f4038808a",
                    "caption": "Our cozy bakery interior",
                    "order": 2,
                    "is_primary": False
                }
            ]
        },
        "content": {
            "about": {
                "html": """<h2>Welcome to Morning Star Bakery &amp; General Store</h2>
<p>Nestled in the heart of Gomti Nagar, <strong>Morning Star Bakery &amp; General Store</strong> has been serving the community since <span style='color: #FF6B6B; font-weight: bold;'>1985</span>. We are a <strong>third-generation family business</strong> committed to providing freshly baked goods and quality groceries to our neighborhood.</p>

<p>Our bakery opens its doors at <em>6:00 AM every morning</em>, filling the air with the irresistible aroma of freshly baked bread, croissants, and traditional Indian sweets. Beyond our bakery, we stock a carefully curated selection of daily essentials, ensuring you find everything you need under one roof.</p>

<h3>What Makes Us Special</h3>
<ul>
  <li><strong>100% Fresh Ingredients:</strong> No preservatives, no artificial flavors</li>
  <li><strong>Traditional Recipes:</strong> Passed down through three generations</li>
  <li><strong>Community First:</strong> Supporting local suppliers and farmers</li>
  <li><strong>Daily Fresh:</strong> Everything baked fresh every morning</li>
</ul>""",
                "plain_text": "Welcome to Morning Star Bakery & General Store. Serving the community since 1985...",
                "last_updated": datetime.now().isoformat(),
                "updated_by": "system"
            },
            "story": {
                "html": """<h2>Our Journey: From a Small Bakery to Your Neighborhood Favorite</h2>

<h3>1985: The Beginning</h3>
<p>It all started with <strong>Mr. Rajesh Kumar Sharma</strong>, a young baker with a dream and a family recipe book. Armed with just <span style='color: #4CAF50;'>₹5,000</span> and an old oven, he opened a tiny 300 sq ft bakery in Gomti Nagar Extension.</p>

<p><em>"I wanted to bring the taste of authentic, home-style baking to our community. Every loaf of bread, every sweet, had to remind people of their grandmother's kitchen."</em> - Rajesh Kumar Sharma, Founder</p>

<h3>1995: Expanding Horizons</h3>
<p>After a decade of hard work and word-of-mouth reputation, we expanded into a <strong>general store</strong>, adding daily essentials alongside our bakery items. This was when Mrs. Sunita Sharma, Rajesh's wife, joined the business full-time, bringing her expertise in customer service.</p>

<h3>2010: The Next Generation</h3>
<p>Our son, <strong>Amit Sharma</strong>, returned from his hospitality management degree and brought fresh ideas while respecting our traditional roots. He introduced:</p>
<ul>
  <li>Sugar-free and gluten-free options</li>
  <li>Online ordering system</li>
  <li>Home delivery service</li>
  <li>Catering for events</li>
</ul>

<h3>2020: Community Support During Crisis</h3>
<p>During the COVID-19 pandemic, we continued serving our community with <strong>contactless delivery</strong> and donated over <span style='color: #FF6B6B; font-weight: bold;'>500 kg of bread and essentials</span> to those in need. This reinforced why we do what we do - <em>community always comes first</em>.</p>

<h3>Today: Looking Forward</h3>
<p>Now in our <strong>third generation</strong>, with Amit's daughter Priya learning the ropes during summer breaks, we continue our mission: bringing joy through fresh baked goods and serving our community with love and dedication.</p>""",
                "plain_text": "Our Journey: From a Small Bakery to Your Neighborhood Favorite. 1985: The Beginning...",
                "last_updated": datetime.now().isoformat(),
                "updated_by": "system"
            },
            "values": {
                "html": """<h2>Our Core Values</h2>

<div style='background-color: #FFF9E6; padding: 15px; border-left: 4px solid #FFB800; margin: 15px 0;'>
<h3 style='color: #FF6B6B; margin-top: 0;'>🥖 Quality Over Quantity</h3>
<p>We never compromise on ingredient quality. Every item is made with premium ingredients sourced from trusted suppliers. If we wouldn't serve it to our family, we won't serve it to yours.</p>
</div>

<div style='background-color: #E8F5E9; padding: 15px; border-left: 4px solid #4CAF50; margin: 15px 0;'>
<h3 style='color: #4CAF50; margin-top: 0;'>🌾 Supporting Local</h3>
<p>We source 80% of our ingredients from <strong>local farmers and suppliers</strong> within Uttar Pradesh. This ensures freshness while supporting our agricultural community. From wheat to dairy to fresh produce - local first, always.</p>
</div>

<div style='background-color: #E3F2FD; padding: 15px; border-left: 4px solid #2196F3; margin: 15px 0;'>
<h3 style='color: #2196F3; margin-top: 0;'>💚 Community Care</h3>
<p>Every month, we donate <strong>50 kg of bread and baked goods</strong> to local shelters and old age homes. We also sponsor education for 5 underprivileged children in our neighborhood.</p>
</div>

<div style='background-color: #FCE4EC; padding: 15px; border-left: 4px solid #E91E63; margin: 15px 0;'>
<h3 style='color: #E91E63; margin-top: 0;'>👨‍👩‍👧‍👦 Family First</h3>
<p>We treat our customers like <em>extended family</em>. Many of our regular customers have been with us for over 20 years! We remember your preferences, celebrate your milestones, and genuinely care about your wellbeing.</p>
</div>

<div style='background-color: #F3E5F5; padding: 15px; border-left: 4px solid #9C27B0; margin: 15px 0;'>
<h3 style='color: #9C27B0; margin-top: 0;'>🌱 Sustainability</h3>
<p>We use <strong>biodegradable packaging</strong>, minimize food waste by donating unsold items, and encourage customers to bring their own bags. Our commitment to the environment is as strong as our commitment to taste.</p>
</div>""",
                "plain_text": "Our Core Values: Quality Over Quantity, Supporting Local, Community Care, Family First, Sustainability",
                "last_updated": datetime.now().isoformat(),
                "updated_by": "system"
            },
            "trust": {
                "html": """<h2>Why You Can Trust Morning Star</h2>

<h3 style='color: #4CAF50;'>✓ FSSAI Certified</h3>
<p>We are proud holders of <strong>FSSAI License No. 10717025000528</strong>, renewed every year since 2011. Our facility undergoes regular inspections and maintains the highest hygiene standards.</p>

<h3 style='color: #4CAF50;'>✓ 40 Years of Service</h3>
<p>Since 1985, we have served over <span style='color: #FF6B6B; font-weight: bold;'>500,000 customers</span> with zero food safety incidents. Our track record speaks for itself.</p>

<h3 style='color: #4CAF50;'>✓ Transparent Sourcing</h3>
<p>We maintain detailed records of all our suppliers. Ask us where any ingredient comes from, and we'll show you! <em>Transparency builds trust</em>.</p>

<h3 style='color: #4CAF50;'>✓ Daily Quality Checks</h3>
<p>Every morning, before we open, we conduct quality checks on all products. Temperature logs, freshness verification, and taste tests - nothing leaves our counter without approval.</p>

<h3 style='color: #4CAF50;'>✓ Customer Reviews</h3>
<p>With an average rating of <strong>4.7/5 from 1,243 reviews</strong>, our customers trust us and keep coming back. Don't just take our word for it - see what our community says!</p>

<div style='background-color: #E8F5E9; padding: 15px; margin: 20px 0; border-radius: 8px;'>
<p style='font-style: italic; margin: 0;'>"I've been buying bread from Morning Star for 15 years. The quality has never dropped. They truly care about what they serve." - Mrs. Verma, Regular Customer</p>
</div>

<h3>Our Certifications</h3>
<ul>
  <li><strong>FSSAI License:</strong> 10717025000528 (Valid till Dec 2026)</li>
  <li><strong>ISO 22000:2018:</strong> Food Safety Management</li>
  <li><strong>Local Business Award 2023:</strong> Recognized by Lucknow Chamber of Commerce</li>
</ul>""",
                "plain_text": "Why You Can Trust Morning Star: FSSAI Certified, 40 Years of Service, Transparent Sourcing...",
                "last_updated": datetime.now().isoformat(),
                "updated_by": "system"
            }
        }
    }

    # Update the store
    response = stores_table.update_item(
        Key={'id': store_id},
        UpdateExpression='SET media = :media, content = :content',
        ExpressionAttributeValues={
            ':media': content['media'],
            ':content': content['content']
        },
        ReturnValues='UPDATED_NEW'
    )

    print(f"✅ Updated {store_id} - Morning Star Bakery")
    return response

def populate_green_valley():
    """Green Valley Grocery"""
    store_id = "STORE-01K8NJ40V9KFKX2Y2FMK466WFH"

    content = {
        "media": {
            "images": [
                {
                    "url": "https://images.unsplash.com/photo-1488459716781-31db52582fe9",
                    "caption": "Fresh organic produce section",
                    "order": 1,
                    "is_primary": True
                }
            ]
        },
        "content": {
            "about": {
                "html": """<h2>Green Valley Grocery - Your Organic Neighborhood Store</h2>
<p>Welcome to <strong>Green Valley Grocery</strong>, Lucknow's premier destination for <em>organic and locally-sourced groceries</em> since 2015. We believe in <span style='color: #4CAF50; font-weight: bold;'>clean eating, sustainable living, and supporting local farmers</span>.</p>

<p>Located in the peaceful Gomti Nagar Extension, we offer:</p>
<ul>
  <li><strong>100% Certified Organic Produce:</strong> Fresh vegetables and fruits from certified organic farms</li>
  <li><strong>Chemical-Free Staples:</strong> Rice, wheat, pulses without pesticides or chemicals</li>
  <li><strong>Natural Products:</strong> Honey, ghee, oil - all sourced from ethical producers</li>
  <li><strong>Eco-Friendly Packaging:</strong> Paper bags and reusable containers</li>
</ul>

<p><em>"We don't just sell groceries; we promote a healthier lifestyle for you and your family."</em></p>""",
                "plain_text": "Green Valley Grocery - Your Organic Neighborhood Store since 2015...",
                "last_updated": datetime.now().isoformat(),
                "updated_by": "system"
            },
            "story": {
                "html": """<h2>Our Story: From Farm to Family</h2>

<h3>The Inspiration</h3>
<p>Green Valley Grocery was founded by <strong>Priya and Arjun Mehta</strong> in 2015 after Priya's health scare. Diagnosed with severe allergies to pesticides, the couple struggled to find clean, organic produce in Lucknow.</p>

<p><em>"We realized if we were struggling, thousands of other families must be too. That's when we decided to create a solution."</em> - Priya Mehta, Co-founder</p>

<h3>Building the Network</h3>
<p>Arjun, an agricultural engineer, traveled to over 50 farms across Uttar Pradesh, identifying and partnering with farmers who practiced organic farming. We helped 15 farmers transition from chemical to organic farming, providing training and market access.</p>

<h3>Growing Together</h3>
<p>What started as a small 500 sq ft store is now a <strong>thriving community hub</strong>. We:</p>
<ul>
  <li>Support <strong>35+ organic farmers</strong> directly</li>
  <li>Serve <strong>2,000+ regular customers</strong></li>
  <li>Conduct monthly workshops on healthy living</li>
  <li>Donate surplus produce to Meals on Wheels</li>
</ul>

<h3>Our Mission Today</h3>
<p>We continue to expand our organic network, ensuring <span style='color: #4CAF50;'>every rupee you spend supports sustainable agriculture and healthier communities</span>.</p>""",
                "plain_text": "Our Story: From Farm to Family. Founded by Priya and Arjun Mehta in 2015...",
                "last_updated": datetime.now().isoformat(),
                "updated_by": "system"
            },
            "values": {
                "html": """<h2>What We Stand For</h2>

<div style='background-color: #E8F5E9; padding: 15px; border-left: 4px solid #4CAF50; margin: 15px 0;'>
<h3 style='color: #4CAF50;'>🌱 100% Organic Promise</h3>
<p>Every product carrying our label is <strong>certified organic</strong>. We personally verify each supplier and maintain traceability from farm to store.</p>
</div>

<div style='background-color: #FFF9E6; padding: 15px; border-left: 4px solid #FFB800; margin: 15px 0;'>
<h3 style='color: #FF8A00;'>🤝 Fair Trade Practices</h3>
<p>We pay farmers <strong>15-20% above market rates</strong> to ensure they receive fair compensation for their labor and commitment to organic practices.</p>
</div>

<div style='background-color: #E3F2FD; padding: 15px; border-left: 4px solid #2196F3; margin: 15px 0;'>
<h3 style='color: #2196F3;'>♻️ Zero Waste Goal</h3>
<p>We compost all organic waste, use biodegradable packaging, and encourage customers to bring reusable bags. Our goal: <em>zero plastic by 2025</em>.</p>
</div>

<div style='background-color: #FCE4EC; padding: 15px; border-left: 4px solid #E91E63; margin: 15px 0;'>
<h3 style='color: #E91E63;'>💚 Health is Wealth</h3>
<p>We believe access to clean, healthy food is a <strong>fundamental right</strong>. That's why we offer subsid ized rates for senior citizens and low-income families.</p>
</div>""",
                "plain_text": "What We Stand For: 100% Organic Promise, Fair Trade Practices, Zero Waste Goal, Health is Wealth",
                "last_updated": datetime.now().isoformat(),
                "updated_by": "system"
            },
            "trust": {
                "html": """<h2>Why Trust Green Valley Grocery?</h2>

<h3 style='color: #4CAF50;'>✓ Triple Certified</h3>
<ul>
  <li><strong>FSSAI Organic Certification</strong></li>
  <li><strong>India Organic (Jaivik Bharat)</strong></li>
  <li><strong>NPOP (National Programme for Organic Production)</strong></li>
</ul>

<h3 style='color: #4CAF50;'>✓ Complete Traceability</h3>
<p>Every product has a <strong>QR code</strong> you can scan to see exactly which farm it came from, when it was harvested, and the certification details. <em>Complete transparency, always</em>.</p>

<h3 style='color: #4CAF50;'>✓ Third-Party Testing</h3>
<p>We send random samples to <strong>accredited laboratories</strong> monthly to test for pesticide residues. All our test reports are publicly available on request.</p>

<h3 style='color: #4CAF50;'>✓ Customer Testimonials</h3>
<div style='background-color: #E8F5E9; padding: 15px; margin: 20px 0; border-radius: 8px;'>
<p style='font-style: italic; margin: 0;'>"After switching to Green Valley's organic produce, my son's allergies reduced significantly. I can't thank them enough!" - Dr. Sharma</p>
</div>

<h3>Visit Our Farm Partners</h3>
<p>We organize <strong>monthly farm visits</strong> for customers to meet the farmers who grow your food. See organic farming in action and build connections!</p>""",
                "plain_text": "Why Trust Green Valley Grocery? Triple Certified, Complete Traceability, Third-Party Testing...",
                "last_updated": datetime.now().isoformat(),
                "updated_by": "system"
            }
        }
    }

    # Update the store
    response = stores_table.update_item(
        Key={'id': store_id},
        UpdateExpression='SET media = :media, content = :content',
        ExpressionAttributeValues={
            ':media': content['media'],
            ':content': content['content']
        },
        ReturnValues='UPDATED_NEW'
    )

    print(f"✅ Updated {store_id} - Green Valley Grocery")
    return response

def populate_tech_hub():
    """Tech Hub Electronics"""
    store_id = "STORE-01K8NJ40V9KFKX2Y2FMK466WFJ"

    content = {
        "media": {
            "images": [
                {
                    "url": "https://images.unsplash.com/photo-1531297484001-80022131f5a1",
                    "caption": "Wide range of latest electronics",
                    "order": 1,
                    "is_primary": True
                }
            ]
        },
        "content": {
            "about": {
                "html": """<h2>Tech Hub Electronics - Your Technology Partner</h2>
<p>Welcome to <strong>Tech Hub Electronics</strong>, Gomti Nagar Extension's most trusted electronics and gadgets store since 2018. We bring <span style='color: #2196F3; font-weight: bold;'>cutting-edge technology</span> with <em>unbeatable prices and exceptional service</em>.</p>

<p>From smartphones to home appliances, laptops to smart home devices, we stock:</p>
<ul>
  <li><strong>Latest Models:</strong> Always up-to-date with newest launches</li>
  <li><strong>Authorized Dealer:</strong> Official warranty on all products</li>
  <li><strong>Expert Guidance:</strong> Our tech experts help you choose wisely</li>
  <li><strong>After-Sales Service:</strong> Free setup and 1-year support</li>
  <li><strong>EMI Options:</strong> Flexible payment plans available</li>
</ul>

<p><em>"Smart tech, smart prices - that's our promise!"</em></p>""",
                "plain_text": "Tech Hub Electronics - Your Technology Partner since 2018...",
                "last_updated": datetime.now().isoformat(),
                "updated_by": "system"
            },
            "story": {
                "html": """<h2>Our Journey in the Tech World</h2>

<h3>2018: The Digital Dream</h3>
<p><strong>Rahul Gupta</strong>, a software engineer turned entrepreneur, noticed that people in Gomti Nagar Extension had to travel far to buy quality electronics. With a passion for technology and customer service, he opened Tech Hub in a modest 800 sq ft space.</p>

<h3>Building Trust Through Service</h3>
<p>Unlike other electronics stores, Rahul introduced:</p>
<ul>
  <li><strong>Free Home Setup:</strong> We don't just sell; we set up your devices</li>
  <li><strong>Extended Support:</strong> Call us anytime with tech questions - even after warranty</li>
  <li><strong>Price Match Guarantee:</strong> Found it cheaper? We'll match the price</li>
  <li><strong>Trade-In Program:</strong> Exchange your old device for credit</li>
</ul>

<h3>Community Tech Hub</h3>
<p>We've become more than a store - we're a <strong>community technology center</strong>:</p>
<ul>
  <li>Free smartphone tutorials for senior citizens every Sunday</li>
  <li>Quarterly workshops on digital literacy</li>
  <li>Partnerships with 15+ schools for student discounts</li>
  <li>Donated 50+ laptops to underprivileged students during COVID</li>
</ul>

<h3>Today and Tomorrow</h3>
<p>With over <span style='color: #2196F3; font-weight: bold;'>15,000 satisfied customers</span> and counting, we continue innovating our service model. Our mission: <em>Make technology accessible, affordable, and understandable for everyone</em>.</p>""",
                "plain_text": "Our Journey in the Tech World. 2018: The Digital Dream. Founded by Rahul Gupta...",
                "last_updated": datetime.now().isoformat(),
                "updated_by": "system"
            },
            "values": {
                "html": """<h2>Our Core Principles</h2>

<div style='background-color: #E3F2FD; padding: 15px; border-left: 4px solid #2196F3; margin: 15px 0;'>
<h3 style='color: #2196F3;'>💡 Technology for All</h3>
<p>We believe <strong>everyone deserves access to technology</strong>, regardless of age or tech-savviness. That's why we offer free tutorials, patient guidance, and lifetime support.</p>
</div>

<div style='background-color: #FFF9E6; padding: 15px; border-left: 4px solid #FFB800; margin: 15px 0;'>
<h3 style='color: #FF8A00;'>🎯 Honest Recommendations</h3>
<p>We never push expensive products. Our experts recommend what's <em>best for your needs and budget</em>, even if it means lower margins for us. Your trust is worth more than any sale.</p>
</div>

<div style='background-color: #E8F5E9; padding: 15px; border-left: 4px solid #4CAF50; margin: 15px 0;'>
<h3 style='color: #4CAF50;'>🔧 Service Beyond Sale</h3>
<p>The sale is just the beginning of our relationship. We provide <strong>free lifetime consultation</strong> - call us anytime with questions about any gadget (even if you didn't buy it from us!).</p>
</div>

<div style='background-color: #FCE4EC; padding: 15px; border-left: 4px solid #E91E63; margin: 15px 0;'>
<h3 style='color: #E91E63;'>🌟 Quality Assurance</h3>
<p>Every product is <strong>100% genuine with official warranty</strong>. We test each item before delivery and offer 7-day return guarantee if you're not satisfied.</p>
</div>""",
                "plain_text": "Our Core Principles: Technology for All, Honest Recommendations, Service Beyond Sale, Quality Assurance",
                "last_updated": datetime.now().isoformat(),
                "updated_by": "system"
            },
            "trust": {
                "html": """<h2>Why Tech Hub is Your Best Choice</h2>

<h3 style='color: #2196F3;'>✓ Authorized Dealer</h3>
<p>Official authorized dealer for <strong>Samsung, Xiaomi, OnePlus, LG, Sony, HP, Dell</strong> and 20+ other brands. All products come with manufacturer warranty.</p>

<h3 style='color: #2196F3;'>✓ Transparent Pricing</h3>
<p>Our prices are displayed clearly with <strong>no hidden charges</strong>. What you see is what you pay. We also offer price match guarantee.</p>

<h3 style='color: #2196F3;'>✓ Certified Technicians</h3>
<p>Our service team consists of <strong>manufacturer-certified technicians</strong> with 10+ years experience. Your devices are in expert hands.</p>

<h3 style='color: #2196F3;'>✓ Customer Reviews</h3>
<div style='background-color: #E3F2FD; padding: 15px; margin: 20px 0; border-radius: 8px;'>
<p style='font-style: italic; margin: 0;'>"Rahul and his team went above and beyond. They not only sold me a laptop but set it up, installed software, and even came back next day when I had questions. Best service ever!" - Anjali Verma</p>
</div>

<h3 style='color: #2196F3;'>✓ Awards & Recognition</h3>
<ul>
  <li><strong>Best Electronics Retailer 2023</strong> - Lucknow Business Awards</li>
  <li><strong>Customer Service Excellence 2022</strong> - Retail Association of India</li>
  <li><strong>5 Star Google Rating</strong> - 950+ reviews</li>
</ul>

<h3>Our Guarantee</h3>
<p style='background-color: #FFE082; padding: 15px; border-radius: 8px; font-weight: bold; text-align: center;'>
Buy with confidence - 7 day return, free servicing, lifetime support!
</p>""",
                "plain_text": "Why Tech Hub is Your Best Choice: Authorized Dealer, Transparent Pricing, Certified Technicians...",
                "last_updated": datetime.now().isoformat(),
                "updated_by": "system"
            }
        }
    }

    # Update the store
    response = stores_table.update_item(
        Key={'id': store_id},
        UpdateExpression='SET media = :media, content = :content',
        ExpressionAttributeValues={
            ':media': content['media'],
            ':content': content['content']
        },
        ReturnValues='UPDATED_NEW'
    )

    print(f"✅ Updated {store_id} - Tech Hub Electronics")
    return response

if __name__ == "__main__":
    print("🚀 Populating stores with rich content...")
    print("=" * 50)

    try:
        populate_morning_star()
        populate_green_valley()
        populate_tech_hub()

        print("=" * 50)
        print("✅ All stores updated successfully!")
        print("\nStores now have:")
        print("  - Media (images/videos)")
        print("  - Rich HTML content for About, Story, Values, Trust tabs")
        print("\nReady to view on the frontend! 🎉")

    except Exception as e:
        print(f"❌ Error: {e}")
        raise
