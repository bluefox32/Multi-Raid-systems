#!/usr/bin/env python3
"""
RAID 100 Simulator
12台構成: RAID 1 (6ペア) → RAID 10 (3グループ) → RAID 0 (最上位)

構成:
    RAID 0 (Top Level)
    /     |     \
RAID10① RAID10② RAID10③
  /\      /\      /\
 R1 R1   R1 R1   R1 R1
 /\ /\   /\ /\   /\ /\
D0 D1    D4 D5   D8 D9
D2 D3    D6 D7   D10 D11
"""

import hashlib
from typing import List, Optional, Dict
from dataclasses import dataclass, field


@dataclass
class StorageDevice:
    """仮想ストレージデバイス（メモリチャンク）"""
    device_id: int
    capacity: int  # チャンク数
    chunks: Dict[int, bytes] = field(default_factory=dict)
    is_failed: bool = False
    
    def write_chunk(self, chunk_id: int, data: bytes) -> bool:
        """チャンクにデータを書き込む"""
        if self.is_failed:
            return False
        if chunk_id >= self.capacity:
            raise ValueError(f"Chunk ID {chunk_id} exceeds capacity {self.capacity}")
        self.chunks[chunk_id] = data
        return True
    
    def read_chunk(self, chunk_id: int) -> Optional[bytes]:
        """チャンクからデータを読み取る"""
        if self.is_failed:
            return None
        return self.chunks.get(chunk_id)
    
    def fail(self):
        """デバイスを故障状態にする"""
        self.is_failed = True
        print(f"⚠️  Device {self.device_id} has FAILED")
    
    def recover(self):
        """デバイスを復旧する"""
        self.is_failed = False
        self.chunks.clear()
        print(f"✅ Device {self.device_id} has been RECOVERED")


class RAID1:
    """RAID 1 (ミラーリング)"""
    def __init__(self, device1: StorageDevice, device2: StorageDevice, raid_id: int):
        self.device1 = device1
        self.device2 = device2
        self.raid_id = raid_id
        self.capacity = min(device1.capacity, device2.capacity)
    
    def write(self, chunk_id: int, data: bytes) -> bool:
        """両方のデバイスに書き込む"""
        result1 = self.device1.write_chunk(chunk_id, data)
        result2 = self.device2.write_chunk(chunk_id, data)
        return result1 or result2  # どちらか一方が成功すればOK
    
    def read(self, chunk_id: int) -> Optional[bytes]:
        """優先的にdevice1から読み、失敗したらdevice2から"""
        data = self.device1.read_chunk(chunk_id)
        if data is None:
            data = self.device2.read_chunk(chunk_id)
        return data
    
    def is_operational(self) -> bool:
        """少なくとも1台が動作していればOK"""
        return not (self.device1.is_failed and self.device2.is_failed)


class RAID10:
    """RAID 10 (RAID 1のペアをRAID 0でストライピング)"""
    def __init__(self, raid1_pairs: List[RAID1], raid_id: int):
        self.raid1_pairs = raid1_pairs
        self.raid_id = raid_id
        self.num_pairs = len(raid1_pairs)
        self.capacity = min(r.capacity for r in raid1_pairs) * self.num_pairs
    
    def write(self, logical_chunk_id: int, data: bytes) -> bool:
        """データをストライピングして書き込む"""
        pair_index = logical_chunk_id % self.num_pairs
        physical_chunk_id = logical_chunk_id // self.num_pairs
        return self.raid1_pairs[pair_index].write(physical_chunk_id, data)
    
    def read(self, logical_chunk_id: int) -> Optional[bytes]:
        """ストライピングされたデータを読み取る"""
        pair_index = logical_chunk_id % self.num_pairs
        physical_chunk_id = logical_chunk_id // self.num_pairs
        return self.raid1_pairs[pair_index].read(physical_chunk_id)
    
    def is_operational(self) -> bool:
        """すべてのRAID1ペアが動作していればOK"""
        return all(pair.is_operational() for pair in self.raid1_pairs)


class RAID100:
    """
    RAID 100 (RAID 10グループをRAID 0でストライピング)
    12台構成: 3つのRAID 10グループ、各グループは2つのRAID 1ペア
    """
    def __init__(self, devices: List[StorageDevice]):
        if len(devices) != 12:
            raise ValueError("RAID 100 requires exactly 12 devices")
        
        self.devices = devices
        
        # RAID 1ペアを6つ作成 (デバイス0-1, 2-3, 4-5, 6-7, 8-9, 10-11)
        self.raid1_pairs = []
        for i in range(6):
            raid1 = RAID1(devices[i*2], devices[i*2+1], raid_id=i)
            self.raid1_pairs.append(raid1)
        
        # RAID 10グループを3つ作成
        self.raid10_groups = []
        for i in range(3):
            raid10 = RAID10([self.raid1_pairs[i*2], self.raid1_pairs[i*2+1]], raid_id=i)
            self.raid10_groups.append(raid10)
        
        self.num_groups = len(self.raid10_groups)
        self.capacity = min(r.capacity for r in self.raid10_groups) * self.num_groups
        
        print(f"🏗️  RAID 100 initialized with {len(devices)} devices")
        print(f"   ├─ 6 × RAID 1 pairs")
        print(f"   ├─ 3 × RAID 10 groups")
        print(f"   └─ Total logical capacity: {self.capacity} chunks")
    
    def write(self, logical_chunk_id: int, data: bytes) -> bool:
        """RAID 100全体にデータを書き込む"""
        if logical_chunk_id >= self.capacity:
            raise ValueError(f"Chunk ID {logical_chunk_id} exceeds capacity {self.capacity}")
        
        # どのRAID 10グループに書き込むか決定
        group_index = logical_chunk_id % self.num_groups
        group_chunk_id = logical_chunk_id // self.num_groups
        
        return self.raid10_groups[group_index].write(group_chunk_id, data)
    
    def read(self, logical_chunk_id: int) -> Optional[bytes]:
        """RAID 100全体からデータを読み取る"""
        if logical_chunk_id >= self.capacity:
            raise ValueError(f"Chunk ID {logical_chunk_id} exceeds capacity {self.capacity}")
        
        group_index = logical_chunk_id % self.num_groups
        group_chunk_id = logical_chunk_id // self.num_groups
        
        return self.raid10_groups[group_index].read(group_chunk_id)
    
    def is_operational(self) -> bool:
        """すべてのRAID 10グループが動作していればOK"""
        return all(group.is_operational() for group in self.raid10_groups)
    
    def get_status(self) -> Dict:
        """RAID 100の状態を取得"""
        return {
            'operational': self.is_operational(),
            'capacity': self.capacity,
            'failed_devices': [d.device_id for d in self.devices if d.is_failed],
            'raid10_statuses': [
                {
                    'group_id': i,
                    'operational': group.is_operational(),
                    'raid1_statuses': [
                        {
                            'pair_id': j,
                            'operational': pair.is_operational(),
                            'devices': [pair.device1.device_id, pair.device2.device_id],
                            'failed': [
                                pair.device1.device_id if pair.device1.is_failed else None,
                                pair.device2.device_id if pair.device2.is_failed else None
                            ]
                        }
                        for j, pair in enumerate(group.raid1_pairs)
                    ]
                }
                for i, group in enumerate(self.raid10_groups)
            ]
        }
    
    def print_status(self):
        """RAID 100の状態を視覚的に表示"""
        print("\n" + "="*60)
        print("RAID 100 Status")
        print("="*60)
        
        status = self.get_status()
        print(f"Overall Status: {'✅ OPERATIONAL' if status['operational'] else '❌ FAILED'}")
        print(f"Total Capacity: {status['capacity']} chunks")
        print(f"Failed Devices: {status['failed_devices'] if status['failed_devices'] else 'None'}")
        print()
        
        for group_status in status['raid10_statuses']:
            group_id = group_status['group_id']
            print(f"RAID 10 Group {group_id}: {'✅' if group_status['operational'] else '❌'}")
            
            for raid1_status in group_status['raid1_statuses']:
                pair_id = raid1_status['pair_id']
                dev1, dev2 = raid1_status['devices']
                failed = [f for f in raid1_status['failed'] if f is not None]
                
                status_icon = '✅' if raid1_status['operational'] else '❌'
                failed_str = f" (Failed: {failed})" if failed else ""
                print(f"  ├─ RAID 1 Pair {pair_id}: {status_icon} [D{dev1}, D{dev2}]{failed_str}")
        
        print("="*60 + "\n")


def main():
    """RAID 100のデモンストレーション"""
    
    # 12台のストレージデバイスを作成（各100チャンク）
    print("🚀 Creating 12 storage devices...")
    devices = [StorageDevice(device_id=i, capacity=100) for i in range(12)]
    
    # RAID 100を構築
    raid100 = RAID100(devices)
    raid100.print_status()
    
    # テストデータを書き込む
    print("📝 Writing test data...")
    test_data = []
    for i in range(20):
        data = f"Test data chunk {i}".encode('utf-8')
        test_data.append(data)
        raid100.write(i, data)
    print(f"   ✅ Written {len(test_data)} chunks\n")
    
    # データを読み取る
    print("📖 Reading test data...")
    for i in range(5):
        data = raid100.read(i)
        if data:
            print(f"   Chunk {i}: {data.decode('utf-8')}")
    print()
    
    # デバイス故障シミュレーション
    print("💥 Simulating device failures...\n")
    
    # シナリオ1: 1台故障（同じRAID 1ペア内）
    print("Scenario 1: Device 0 fails (RAID 1 pair with Device 1)")
    devices[0].fail()
    raid100.print_status()
    
    # データがまだ読めることを確認
    print("Verifying data integrity after 1 failure...")
    data = raid100.read(0)
    if data:
        print(f"   ✅ Data still readable: {data.decode('utf-8')}\n")
    
    # シナリオ2: 同じペアのもう1台も故障
    print("Scenario 2: Device 1 also fails (same RAID 1 pair)")
    devices[1].fail()
    raid100.print_status()
    
    # データが読めなくなることを確認
    print("Verifying data integrity after 2 failures in same pair...")
    data = raid100.read(0)
    if data is None:
        print(f"   ❌ Data lost for chunk 0 (expected behavior)\n")
    
    # 他のチャンクは読めることを確認
    print("Checking other chunks...")
    data = raid100.read(1)
    if data:
        print(f"   ✅ Chunk 1 still readable: {data.decode('utf-8')}")
    
    data = raid100.read(2)
    if data:
        print(f"   ✅ Chunk 2 still readable: {data.decode('utf-8')}\n")
    
    # シナリオ3: 異なるRAID 1ペアで故障
    print("Scenario 3: Device 4 fails (different RAID 1 pair)")
    devices[4].fail()
    raid100.print_status()
    
    # まだデータが読めることを確認
    print("Verifying data integrity...")
    data = raid100.read(2)
    if data:
        print(f"   ✅ Chunk 2 still readable: {data.decode('utf-8')}\n")
    
    # 容量効率の計算
    print("📊 Capacity Analysis:")
    total_raw = sum(d.capacity for d in devices)
    usable = raid100.capacity
    efficiency = (usable / total_raw) * 100
    print(f"   Raw capacity: {total_raw} chunks")
    print(f"   Usable capacity: {usable} chunks")
    print(f"   Efficiency: {efficiency:.1f}%")
    print(f"   Redundancy: {total_raw - usable} chunks used for mirroring")


if __name__ == "__main__":
    main()
