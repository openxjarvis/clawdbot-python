import csv
import random
from datetime import datetime, timedelta

# 定义维度
regions = {
    "华北": ["北京", "天津", "河北"],
    "华东": ["上海", "江苏", "浙江"],
    "华南": ["广东", "广西", "福建"]
}
products = {
    "电子产品": ["笔记本电脑", "智能手机", "平板电脑"],
    "办公用品": ["复印纸", "打印机", "订书机"],
    "家具": ["办公椅", "会议桌", "文件柜"]
}
sales_people = ["张三", "李四", "王五", "赵六", "孙七"]

# 生成数据
data = []
header = ["日期", "大区", "省份/直辖市", "产品类别", "具体产品", "销售员", "销售数量", "单价(元)", "销售总额(元)"]
data.append(header)

base_date = datetime(2023, 1, 1)

for _ in range(100):
    # 随机生成日期
    date = base_date + timedelta(days=random.randint(0, 365))
    date_str = date.strftime("%Y-%m-%d")
    
    # 随机生成地区维度
    region = random.choice(list(regions.keys()))
    province = random.choice(regions[region])
    
    # 随机生成产品维度
    category = random.choice(list(products.keys()))
    product = random.choice(products[category])
    
    # 随机生成人员
    person = random.choice(sales_people)
    
    # 随机生成数值
    quantity = random.randint(1, 20)
    price = random.randint(100, 10000)
    total = quantity * price
    
    data.append([
        date_str, region, province, category, product, person, quantity, price, total
    ])

# 写入文件
filename = "sales_multidimensional_data.csv"
with open(filename, "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.writer(f)
    writer.writerows(data)

print(f"Generated {filename}")
