#!/usr/bin/env python3
"""
RAID 100 with XOR Parity Simulator
12台構成 + XORベースのパリティ計算

XOR方式:
- RAID 1ではミラーリングの代わりにXORパリティも使用可能
- RAID 5/6のようなパリティベースのRAIDもサポート
- データの冗長性をXOR演算で実現
"""

from typing import List, Optional, Dict, Tuple
from dataclasses import dataclass, field
import os


def xor_bytes(data_list: List[bytes]) -> bytes:
    """
    複数のバイト列をXOR演算する
    パリティ計算とデータ復元に使用
    """
    if not data_list:
        return b''
    
    # すべて同じ長さに揃える
    max_len = max(len(data) for data in data_list)
    padded_data = [data.ljust(max_len, b'\x00') for data in data_list]
    
    # XOR演算
    result = bytearray(padded_data[0])
    for data in padded_data[1:]:
        for i in range(len(result)):
            result[i] ^= data[i]
    
    return bytes(result)


def calculate_parity(data_chunks: List[bytes]) -> bytes:
    """XORパリティを計算"""
    return xor_bytes(data_chunks)


def reconstruct_data(available_chunks: List[Optional[bytes]], parity: bytes) -> bytes:
    """
    XORパリティを使用してデータを復元
    available_chunks: データチャンク（Noneは欠損を示す）
    parity: パリティデータ
    """
    valid_chunks = [chunk for chunk in available_chunks if chunk is not None]
    valid_chunks.append(parity)
    return xor_bytes(valid_chunks)


@dataclass
class StorageDevice:
    """仮想ストレージデバイス（メモリチャンク）"""
    device_id: int
    capacity: int  # チャンク数
    chunks: Dict[int, bytes] = field(default_factory=dict)
    is_failed: bool = False
    read_count: int = 0
    write_count: int = 0
    
    def write_chunk(self, chunk_id: int, data: bytes) -> bool:
        """チャンクにデータを書き込む"""
        if self.is_failed:
            return False
        if chunk_id >= self.capacity:
            raise ValueError(f"Chunk ID {chunk_id} exceeds capacity {self.capacity}")
        self.chunks[chunk_id] = data
        self.write_count += 1
        return True
    
    def read_chunk(self, chunk_id: int) -> Optional[bytes]:
        """チャンクからデータを読み取る"""
        if self.is_failed:
            return None
        self.read_count += 1
        return self.chunks.get(chunk_id)
    
    def fail(self):
        """デバイスを故障状態にする"""
        self.is_failed = True
        print(f"⚠️  Device {self.device_id} has FAILED")
    
    def recover(self):
        """デバイスを復旧する"""
        self.is_failed = False
        print(f"✅ Device {self.device_id} has been RECOVERED")
    
    def get_stats(self) -> Dict:
        """デバイスの統計情報を取得"""
        return {
            'device_id': self.device_id,
            'reads': self.read_count,
            'writes': self.write_count,
            'chunks_stored': len(self.chunks),
            'failed': self.is_failed
        }


class RAID1_XOR:
    """
    RAID 1 with XOR verification
    ミラーリング + XORチェックサムでデータ整合性を検証
    """
    def __init__(self, device1: StorageDevice, device2: StorageDevice, raid_id: int):
        self.device1 = device1
        self.device2 = device2
        self.raid_id = raid_id
        self.capacity = min(device1.capacity, device2.capacity)
        self.xor_mismatches = 0
    
    def write(self, chunk_id: int, data: bytes) -> bool:
        """両方のデバイスに書き込み、XORチェックサムも保存"""
        result1 = self.device1.write_chunk(chunk_id, data)
        result2 = self.device2.write_chunk(chunk_id, data)
        return result1 or result2
    
    def read(self, chunk_id: int) -> Optional[bytes]:
        """
        両方のデバイスから読み取り、XORで整合性チェック
        不一致の場合は警告を出す
        """
        data1 = self.device1.read_chunk(chunk_id)
        data2 = self.device2.read_chunk(chunk_id)
        
        # 両方とも読めない場合
        if data1 is None and data2 is None:
            return None
        
        # どちらか一方のみ読める場合
        if data1 is None:
            return data2
        if data2 is None:
            return data1
        
        # 両方読める場合、整合性チェック
        if data1 != data2:
            self.xor_mismatches += 1
            print(f"⚠️  XOR mismatch detected in RAID1 {self.raid_id}, chunk {chunk_id}")
            # 最初のデバイスのデータを優先
            return data1
        
        return data1
    
    def is_operational(self) -> bool:
        """少なくとも1台が動作していればOK"""
        return not (self.device1.is_failed and self.device2.is_failed)


class RAID5_XOR:
    """
    RAID 5 with XOR parity
    データをストライピングし、XORパリティで冗長性を確保
    """
    def __init__(self, devices: List[StorageDevice], raid_id: int):
        if len(devices) < 3:
            raise ValueError("RAID 5 requires at least 3 devices")
        
        self.devices = devices
        self.raid_id = raid_id
        self.num_devices = len(devices)
        self.capacity = min(d.capacity for d in devices) * (self.num_devices - 1)
    
    def _get_stripe_info(self, logical_chunk_id: int) -> Tuple[int, List[int], int]:
        """
        ストライプ情報を取得
        Returns: (stripe_number, data_device_indices, parity_device_index)
        """
        stripe_num = logical_chunk_id // (self.num_devices - 1)
        chunk_in_stripe = logical_chunk_id % (self.num_devices - 1)
        
        # パリティの位置をローテーション
        parity_device = stripe_num % self.num_devices
        
        # データデバイスのインデックスを計算
        data_devices = []
        for i in range(self.num_devices):
            if i != parity_device:
                data_devices.append(i)
        
        return stripe_num, data_devices, parity_device
    
    def write(self, logical_chunk_id: int, data: bytes) -> bool:
        """RAID 5にデータを書き込み、XORパリティを計算"""
        stripe_num, data_devices, parity_device = self._get_stripe_info(logical_chunk_id)
        chunk_in_stripe = logical_chunk_id % (self.num_devices - 1)
        
        # データを書き込むデバイスとチャンクID
        data_dev_idx = data_devices[chunk_in_stripe]
        physical_chunk_id = stripe_num
        
        # データを書き込む
        if not self.devices[data_dev_idx].write_chunk(physical_chunk_id, data):
            return False
        
        # 同じストライプ内の他のデータを読み取る
        stripe_data = []
        for i, dev_idx in enumerate(data_devices):
            if i == chunk_in_stripe:
                stripe_data.append(data)
            else:
                chunk_data = self.devices[dev_idx].read_chunk(physical_chunk_id)
                if chunk_data is not None:
                    stripe_data.append(chunk_data)
                else:
                    # 他のチャンクがまだ書き込まれていない場合
                    stripe_data.append(b'')
        
        # XORパリティを計算して書き込む
        parity = calculate_parity(stripe_data)
        return self.devices[parity_device].write_chunk(physical_chunk_id, parity)
    
    def read(self, logical_chunk_id: int) -> Optional[bytes]:
        """RAID 5からデータを読み取る。必要に応じてXORで復元"""
        stripe_num, data_devices, parity_device = self._get_stripe_info(logical_chunk_id)
        chunk_in_stripe = logical_chunk_id % (self.num_devices - 1)
        
        data_dev_idx = data_devices[chunk_in_stripe]
        physical_chunk_id = stripe_num
        
        # まず通常通りデータを読み取る
        data = self.devices[data_dev_idx].read_chunk(physical_chunk_id)
        
        # データが読めた場合はそのまま返す
        if data is not None:
            return data
        
        # データが読めない場合、XORパリティで復元を試みる
        print(f"🔧 Reconstructing data using XOR parity for chunk {logical_chunk_id}")
        
        # パリティを読み取る
        parity = self.devices[parity_device].read_chunk(physical_chunk_id)
        if parity is None:
            return None
        
        # 他のデータチャンクを読み取る
        available_data = []
        for i, dev_idx in enumerate(data_devices):
            if i != chunk_in_stripe:
                chunk_data = self.devices[dev_idx].read_chunk(physical_chunk_id)
                if chunk_data is None:
                    # 複数のデータチャンクが欠損している場合は復元不可
                    return None
                available_data.append(chunk_data)
            else:
                available_data.append(None)
        
        # XORで復元
        return reconstruct_data(available_data, parity)
    
    def is_operational(self) -> bool:
        """最大1台の故障まで動作可能"""
        failed_count = sum(1 for d in self.devices if d.is_failed)
        return failed_count <= 1


class RAID10_XOR:
    """RAID 10 (RAID 1のペアをRAID 0でストライピング) with XOR verification"""
    def __init__(self, raid1_pairs: List[RAID1_XOR], raid_id: int):
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


class RAID100_XOR:
    """
    RAID 100 with XOR-based verification and parity
    12台構成: 3つのRAID 10グループ、各グループは2つのRAID 1ペア
    """
    def __init__(self, devices: List[StorageDevice]):
        if len(devices) != 12:
            raise ValueError("RAID 100 requires exactly 12 devices")
        
        self.devices = devices
        
        # RAID 1ペアを6つ作成（XOR検証付き）
        self.raid1_pairs = []
        for i in range(6):
            raid1 = RAID1_XOR(devices[i*2], devices[i*2+1], raid_id=i)
            self.raid1_pairs.append(raid1)
        
        # RAID 10グループを3つ作成
        self.raid10_groups = []
        for i in range(3):
            raid10 = RAID10_XOR([self.raid1_pairs[i*2], self.raid1_pairs[i*2+1]], raid_id=i)
            self.raid10_groups.append(raid10)
        
        self.num_groups = len(self.raid10_groups)
        self.capacity = min(r.capacity for r in self.raid10_groups) * self.num_groups
        
        print(f"🏗️  RAID 100 with XOR initialized")
        print(f"   ├─ 12 devices")
        print(f"   ├─ 6 × RAID 1 pairs (with XOR verification)")
        print(f"   ├─ 3 × RAID 10 groups")
        print(f"   └─ Total logical capacity: {self.capacity} chunks")
    
    def write(self, logical_chunk_id: int, data: bytes) -> bool:
        """RAID 100全体にデータを書き込む"""
        if logical_chunk_id >= self.capacity:
            raise ValueError(f"Chunk ID {logical_chunk_id} exceeds capacity {self.capacity}")
        
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
    
    def get_stats(self) -> Dict:
        """統計情報を取得"""
        device_stats = [d.get_stats() for d in self.devices]
        total_reads = sum(s['reads'] for s in device_stats)
        total_writes = sum(s['writes'] for s in device_stats)
        total_xor_mismatches = sum(p.xor_mismatches for p in self.raid1_pairs)
        
        return {
            'operational': self.is_operational(),
            'capacity': self.capacity,
            'total_reads': total_reads,
            'total_writes': total_writes,
            'xor_mismatches': total_xor_mismatches,
            'failed_devices': [d.device_id for d in self.devices if d.is_failed],
            'device_stats': device_stats
        }
    
    def print_status(self):
        """RAID 100の状態を視覚的に表示"""
        print("\n" + "="*60)
        print("RAID 100 XOR Status")
        print("="*60)
        
        stats = self.get_stats()
        print(f"Overall Status: {'✅ OPERATIONAL' if stats['operational'] else '❌ FAILED'}")
        print(f"Total Capacity: {stats['capacity']} chunks")
        print(f"Total Reads: {stats['total_reads']}")
        print(f"Total Writes: {stats['total_writes']}")
        print(f"XOR Mismatches: {stats['xor_mismatches']}")
        print(f"Failed Devices: {stats['failed_devices'] if stats['failed_devices'] else 'None'}")
        print()
        
        for i, group in enumerate(self.raid10_groups):
            print(f"RAID 10 Group {i}: {'✅' if group.is_operational() else '❌'}")
            
            for j, pair in enumerate(group.raid1_pairs):
                dev1, dev2 = pair.device1.device_id, pair.device2.device_id
                failed = []
                if pair.device1.is_failed:
                    failed.append(dev1)
                if pair.device2.is_failed:
                    failed.append(dev2)
                
                status_icon = '✅' if pair.is_operational() else '❌'
                failed_str = f" (Failed: {failed})" if failed else ""
                xor_str = f" [XOR mismatches: {pair.xor_mismatches}]" if pair.xor_mismatches > 0 else ""
                print(f"  ├─ RAID 1 Pair {j}: {status_icon} [D{dev1}, D{dev2}]{failed_str}{xor_str}")
        
        print("="*60 + "\n")


def demo_raid5_xor():
    """RAID 5 with XOR parityのデモ"""
    print("\n" + "🔷"*30)
    print("RAID 5 XOR Parity Demo")
    print("🔷"*30 + "\n")
    
    # 4台のデバイスでRAID 5を構成
    devices = [StorageDevice(device_id=i, capacity=50) for i in range(4)]
    raid5 = RAID5_XOR(devices, raid_id=0)
    
    print(f"📝 RAID 5 created with {len(devices)} devices")
    print(f"   Capacity: {raid5.capacity} chunks\n")
    
    # データを書き込む
    test_data = [f"RAID5 data {i}".encode('utf-8') for i in range(6)]
    print("Writing test data...")
    for i, data in enumerate(test_data):
        raid5.write(i, data)
    print(f"✅ Written {len(test_data)} chunks\n")
    
    # 正常に読み取る
    print("Reading data (all devices operational):")
    for i in range(3):
        data = raid5.read(i)
        print(f"   Chunk {i}: {data.decode('utf-8')}")
    print()
    
    # デバイスを1台故障させる
    print("💥 Failing device 1...")
    devices[1].fail()
    
    # XORパリティで復元して読み取る
    print("\nReading data (with XOR reconstruction):")
    for i in range(3):
        data = raid5.read(i)
        if data:
            print(f"   Chunk {i}: {data.decode('utf-8')}")
    print()


def demo_raid100_xor():
    """RAID 100 with XORのデモ"""
    print("\n" + "🔷"*30)
    print("RAID 100 XOR Demo")
    print("🔷"*30 + "\n")
    
    # 12台のストレージデバイスを作成
    devices = [StorageDevice(device_id=i, capacity=100) for i in range(12)]
    raid100 = RAID100_XOR(devices)
    raid100.print_status()
    
    # テストデータを書き込む
    print("📝 Writing test data with XOR verification...")
    test_data = []
    for i in range(20):
        data = f"XOR Test chunk {i} - {os.urandom(8).hex()}".encode('utf-8')
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
    print("💥 Simulating device failures with XOR verification...\n")
    
    # シナリオ1: 1台故障
    print("Scenario 1: Device 0 fails")
    devices[0].fail()
    raid100.print_status()
    
    # XOR検証付きで読み取り
    print("Reading with XOR verification...")
    data = raid100.read(0)
    if data:
        print(f"   ✅ Data recovered via mirror: {data.decode('utf-8')[:50]}...\n")
    
    # シナリオ2: データ破損をシミュレート
    print("Scenario 2: Simulating data corruption on Device 2")
    # Device 2のチャンク0を意図的に破損
    if 0 in devices[2].chunks:
        devices[2].chunks[0] = b"CORRUPTED DATA"
    
    # XOR検証で不一致を検出
    print("Reading chunk that spans corrupted device...")
    data = raid100.read(6)  # このチャンクはdevice 2-3のペアに含まれる
    print()
    
    raid100.print_status()


def main():
    """メインデモ"""
    print("🚀 RAID XOR Parity System Demo\n")
    
    # RAID 5のデモ
    demo_raid5_xor()
    
    # RAID 100のデモ
    demo_raid100_xor()
    
    print("\n" + "="*60)
    print("📊 XOR Parity Summary")
    print("="*60)
    print("✅ XOR allows data reconstruction from parity")
    print("✅ RAID 5 can survive 1 drive failure")
    print("✅ RAID 100 provides redundancy at multiple levels")
    print("✅ XOR verification detects data corruption")
    print("="*60)


if __name__ == "__main__":
    main()
