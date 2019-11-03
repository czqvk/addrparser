import pandas as pd
import json
import re

class tude_addr_tran():
    '''
        输入经纬度，输出省市区，由于该算法有一点误差，输出的结果可能有多个省市区（极少部分情况下）
    '''
    def __init__(self, region_data, latitude_range = 0.005):
        '''
        :param region_data:传入的region_data数据（包括全国省市区的代号及边界经纬度数据）
        '''
        self.latitude_range = latitude_range
        self.data = region_data
        self.data_dic = self.data_deal()


    def poly_tran(self,ls):
        '''
            将边界经纬度转换成list格式
        '''
        try:
            loc_ls = re.split(string=ls.get('polyline'), pattern='[;|]')
            loc_ls = [[float(x[0]), float(x[1])] for x in [l.split(',') for l in loc_ls]]
            return loc_ls
        except:
            print(ls.get('code'))
            return ''


    def data_deal(self):
        '''
             转换经纬度数据，生成经纬度范围指标
             :return: 转换格式后的数据字典，格式为{110000:{'province':{},'city':{110100:{'district':{110118:{}}}}}
        '''
        #特殊的四个城市的县区放在了第四级地址(可惜它们的第四级地址的边界数据都是一样的)
        # special_city_code = [441900,442000,460400,620200]
        data = self.data
        for da in data:
            da['polyline'] = self.poly_tran(da)
            da['longitude_range'] = [min([s[0] for s in da.get('polyline')]), max([s[0] for s in da.get('polyline')])]
            da['latitude_range'] = [min([s[1] for s in da.get('polyline')]), max([s[1] for s in da.get('polyline')])]

        # 将数据转换成字典格式，生成data_dic字典，格式为{110000:{'province':{},'city':{110100:{'district':{110118:{}}}}}
        data_dic = {d.get('code'): {'province': d} for d in data if d.get('level') == 1}
        for prov_code in data_dic.keys():
            da_p = data_dic[prov_code]
            da_p['city'] = {d.get('code'): d for d in data if (d.get('level') == 2) & (d.get('parentCode') == prov_code)}
            if da_p.get('city'):
                for city_code in da_p['city'].keys():
                    da_p['city'][city_code]['district'] = {d.get('code'): d for d in data if (d.get('level') == 3) & (d.get('parentCode') == city_code)}
        return data_dic


    def lgt_lat_judge(self, longitude, latitude, longitude_range, latitude_range):
        '''
        :param longitude:查询点经度
        :param latitude: 查询点纬度
        :param longitude_range: 所匹配地区的经度范围
        :param latitude_range: 所匹配地区的纬度范围
        :return: 判断查询点是否在匹配区域的经纬度范围内 （方法一）
        '''
        if (longitude < longitude_range[0]) | (longitude > longitude_range[1]) | (latitude < latitude_range[0]) | (
                latitude > latitude_range[1]):
            return False
        else:
            return True


    # 判断查询点纬度上下几百米范围内的边界经度是否包括查询点
    def lgt_check(self,longitude, latitude, data):
        '''
        :param longitude:查询点经度
        :param latitude: 查询点纬度
        :param data: 所匹配地区的边界经纬度数据
        :return: 在与查询点纬度差0.005的纬度范围内，查询所匹配区域边界经度，判断是否在边界经度范围内（方法二）
        '''
        lgt_ls = [l[0] for l in data if abs(latitude - l[1]) < self.latitude_range]
        if len(lgt_ls) == 0:
            return False
        else:
            if (longitude < min(lgt_ls)) | (longitude > max(lgt_ls)):
                return False
            else:
                return True


    # 根据查询点纬度上下几百米范围内的边界经度判断查询点是否在省份或者市区内
    def addr_check(self, longitude, latitude, addr_se, addr_name):
        '''
        :param longitude:查询点经度
        :param latitude: 查询点纬度
        :param addr_se: 通过方法一判断初筛后的候选地址代号，格式示例：[110000, 110100, 110108]
        :param addr_name: 通过方法一判断初筛后的候选地址名字，格式示例：['北京市', '北京城区', '海淀区']
        :return: 方法二判断后筛选后的地址，由于方法精度无法达到100%，有可能出现两个以上地址（无法确定哪个是对的），
                格式示例：[[360000, 360800, 360802]], [['江西省', '吉安市', '吉州区']]
        '''
        addr_check_code = []
        addr_check_name = []
        for i, ad in enumerate(addr_se):
            se_len = len(ad)
            if se_len == 1:
                pro_code, ct_code, dt_code = ad[0], '', ''
            if se_len == 2:
                pro_code, ct_code, dt_code = ad[0], ad[1], ''
            if se_len == 3:
                pro_code, ct_code, dt_code = ad[0], ad[1], ad[2]
            # 验证省份数据
            pro_poly = self.data_dic.get(pro_code).get('province').get('polyline')
            if self.lgt_check(longitude, latitude, pro_poly):
                if ct_code:
                    city_poly = self.data_dic.get(pro_code).get('city').get(ct_code).get('polyline')
                    # 验证城市数据
                    if self.lgt_check(longitude, latitude, city_poly):
                        if dt_code:
                            district_poly = self.data_dic.get(pro_code).get('city').get(ct_code).get('district').get(
                                dt_code).get('polyline')
                            # 验证地区数据
                            if self.lgt_check(longitude, latitude, district_poly):
                                addr_check_code.append(ad)
                                addr_check_name.append(addr_name[i])
                            else:
                                continue
                        else:
                            addr_check_code.append(ad)
                            addr_check_name.append(addr_name[i])
                    else:
                        continue
                else:
                    addr_check_code.append(ad)
                    addr_check_name.append(addr_name[i])
            else:
                continue
        return addr_check_code, addr_check_name


    # 根据省份及城市矩阵初步筛选符合条件的省份及城市（港澳台只做省份的判断）
    def addr_judge(self, longitude, latitude, city_judge=True, district_judge=True):
        '''
        :param longitude: 查询点经度
        :param latitude: 查询点纬度
        :param city_judge: 是否进行城市判断
        :param district_judge: 是否进行区判断
        :return: 通过两个地址判别方法，最终输出地址结果，会输出地址代号和地址名字，
                格式示例：[[360000, 360800, 360802]], [['江西省', '吉安市', '吉州区']]
        '''
        gangaotai_code = [820000, 710000, 810000]
        addr_se = []
        addr_name = []
        for code, val in self.data_dic.items():
            # 判断是否在省份范围内
            if self.lgt_lat_judge(longitude, latitude, val.get('province').get('longitude_range'),
                             val.get('province').get('latitude_range')):
                # 判断是否查看市范围和是否属于港澳台地区
                if (city_judge) & (code not in gangaotai_code):
                    city_se = []
                    city_name = []
                    for city_code, city_val in val.get('city').items():
                        # 判断是否在市范围内
                        if self.lgt_lat_judge(longitude, latitude, city_val.get('longitude_range'),
                                         city_val.get('latitude_range')):
                            if (district_judge) & (len(city_val.get('district')) > 0):
                                # 接着判断是否在该市的区范围内
                                for dis_code, dis_val in city_val.get('district').items():
                                    if self.lgt_lat_judge(longitude, latitude, dis_val.get('longitude_range'),
                                                     dis_val.get('latitude_range')):
                                        addr_se.append([code, city_code, dis_code])
                                        addr_name.append([val.get('province').get('name'), city_val.get('name'),
                                                          dis_val.get('name')])
                                    else:
                                        continue
                            else:
                                addr_se.append([code, city_code])
                                addr_name.append([val.get('province').get('name'), city_val.get('name')])
                        else:
                            continue
                else:
                    addr_se.append([code])
                    addr_name.append([val.get('province').get('name')])
            else:
                continue

        #如果通过方法一初筛后的地址大于两个，则进行方法二在筛选一次，运气好的话最终只有一个地区
        if len(addr_se) > 1:
            addr_check_code, addr_check_name = self.addr_check(longitude, latitude, addr_se, addr_name)
            if len(addr_check_code) == 0:
                return addr_se, addr_name
            else:
                return addr_check_code, addr_check_name
        else:
            return addr_se, addr_name

if __name__ == '__main__':
    # 读取数据
    with open('china-region.json', encoding='utf-8') as f:
        region_data = json.load(f)

    tat = tude_addr_tran(region_data)
    longitude,latitude = 119.963675,31.733606
    a = tat.addr_judge(longitude,latitude)
    print(a)
