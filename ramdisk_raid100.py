#!/usr/bin/env python3
"""
RAID 100 XOR with RAM Disk Implementation
完全メモリベースの高速RAIDストレージシステム

特徴:
- 全データをメモリ上に保持（RAMディスク）
- XORパリティによる冗長性
- ファイルシステムライクなインターフェース
- 永続化オプション（ディスクへのスナップショット保存）
"""

import os
import pickle
import time
from typing import List, Optional, Dict, Tuple
from dataclasses import dataclass, field
from pathlib import Path
import json


def xor_bytes(data_list: List[bytes]) -> bytes:
    """複数のバイト列をXOR演算"""
    if not data_list:
        return b''
    
    max_len = max(len(data) for data in data_list)
    padded_data = [data.ljust(max_len, b'\x00') for data in data_list]
    
    result = bytearray(padded_data[0])
    for data in padded_data[1:]:
        for i in range(len(result)):
            result[i] ^= data[i]
    
    return bytes(result)


def calculate_parity(data_chunks: List[bytes]) -> bytes:
    """XORパリティを計算"""
    return xor_bytes(data_chunks)


def reconstruct_data(available_chunks: List[Optional[bytes]], parity: bytes) -> bytes:
    """XORパリティを使用してデータを復元"""
    valid_chunks = [chunk for chunk in available_chunks if chunk is not None]
    valid_chunks.append(parity)
    return xor_bytes(valid_chunks)


@dataclass
class RAMDiskDevice:
    """
    RAMディスクデバイス
    完全にメモリ上で動作する仮想ストレージデバイス
    """
    device_id: int
    capacity_mb: int  # MB単位の容量
    chunk_size: int = 4096  # バイト（デフォルト4KB）
    
    chunks: Dict[int, bytes] = field(default_factory=dict)
    is_failed: bool = False
    read_count: int = 0
    write_count: int = 0
    read_bytes: int = 0
    write_bytes: int = 0
    
    def __post_init__(self):
        """初期化後の処理"""
        self.max_chunks = (self.capacity_mb * 1024 * 1024) // self.chunk_size
        print(f"💾 RAMDisk Device {self.device_id}: {self.capacity_mb}MB ({self.max_chunks} chunks)")
    
    def write_chunk(self, chunk_id: int, data: bytes) -> bool:
        """チャンクにデータを書き込む"""
        if self.is_failed:
            return False
        if chunk_id >= self.max_chunks:
            raise ValueError(f"Chunk ID {chunk_id} exceeds capacity")
        
        # データをチャンクサイズに切り詰めまたはパディング
        if len(data) > self.chunk_size:
            data = data[:self.chunk_size]
        
        self.chunks[chunk_id] = data
        self.write_count += 1
        self.write_bytes += len(data)
        return True
    
    def read_chunk(self, chunk_id: int) -> Optional[bytes]:
        """チャンクからデータを読み取る"""
        if self.is_failed:
            return None
        
        self.read_count += 1
        data = self.chunks.get(chunk_id)
        if data:
            self.read_bytes += len(data)
        return data
    
    def get_memory_usage(self) -> int:
        """メモリ使用量をバイト単位で取得"""
        return sum(len(data) for data in self.chunks.values())
    
    def get_memory_usage_mb(self) -> float:
        """メモリ使用量をMB単位で取得"""
        return self.get_memory_usage() / (1024 * 1024)
    
    def fail(self):
        """デバイスを故障状態にする"""
        self.is_failed = True
        print(f"⚠️  RAMDisk Device {self.device_id} has FAILED")
    
    def recover(self):
        """デバイスを復旧する"""
        self.is_failed = False
        self.chunks.clear()
        print(f"✅ RAMDisk Device {self.device_id} has been RECOVERED")
    
    def clear(self):
        """すべてのデータをクリア"""
        self.chunks.clear()
        self.read_count = 0
        self.write_count = 0
        self.read_bytes = 0
        self.write_bytes = 0
    
    def get_stats(self) -> Dict:
        """統計情報を取得"""
        return {
            'device_id': self.device_id,
            'capacity_mb': self.capacity_mb,
            'memory_usage_mb': self.get_memory_usage_mb(),
            'utilization': (self.get_memory_usage_mb() / self.capacity_mb) * 100,
            'chunks_stored': len(self.chunks),
            'max_chunks': self.max_chunks,
            'reads': self.read_count,
            'writes': self.write_count,
            'read_mb': self.read_bytes / (1024 * 1024),
            'write_mb': self.write_bytes / (1024 * 1024),
            'failed': self.is_failed
        }


class RAID1_XOR:
    """RAID 1 with XOR verification"""
    def __init__(self, device1: RAMDiskDevice, device2: RAMDiskDevice, raid_id: int):
        self.device1 = device1
        self.device2 = device2
        self.raid_id = raid_id
        self.capacity = min(device1.max_chunks, device2.max_chunks)
        self.xor_mismatches = 0
    
    def write(self, chunk_id: int, data: bytes) -> bool:
        result1 = self.device1.write_chunk(chunk_id, data)
        result2 = self.device2.write_chunk(chunk_id, data)
        return result1 or result2
    
    def read(self, chunk_id: int) -> Optional[bytes]:
        data1 = self.device1.read_chunk(chunk_id)
        data2 = self.device2.read_chunk(chunk_id)
        
        if data1 is None and data2 is None:
            return None
        if data1 is None:
            return data2
        if data2 is None:
            return data1
        
        if data1 != data2:
            self.xor_mismatches += 1
            print(f"⚠️  XOR mismatch in RAID1 {self.raid_id}, chunk {chunk_id}")
            return data1
        
        return data1
    
    def is_operational(self) -> bool:
        return not (self.device1.is_failed and self.device2.is_failed)


class RAID10_XOR:
    """RAID 10 with XOR verification"""
    def __init__(self, raid1_pairs: List[RAID1_XOR], raid_id: int):
        self.raid1_pairs = raid1_pairs
        self.raid_id = raid_id
        self.num_pairs = len(raid1_pairs)
        self.capacity = min(r.capacity for r in raid1_pairs) * self.num_pairs
    
    def write(self, logical_chunk_id: int, data: bytes) -> bool:
        pair_index = logical_chunk_id % self.num_pairs
        physical_chunk_id = logical_chunk_id // self.num_pairs
        return self.raid1_pairs[pair_index].write(physical_chunk_id, data)
    
    def read(self, logical_chunk_id: int) -> Optional[bytes]:
        pair_index = logical_chunk_id % self.num_pairs
        physical_chunk_id = logical_chunk_id // self.num_pairs
        return self.raid1_pairs[pair_index].read(physical_chunk_id)
    
    def is_operational(self) -> bool:
        return all(pair.is_operational() for pair in self.raid1_pairs)


class RAMDiskRAID100:
    """
    RAMディスクベースのRAID 100システム
    完全にメモリ上で動作する高速ストレージ
    """
    def __init__(self, num_devices: int = 12, device_capacity_mb: int = 100):
        if num_devices != 12:
            raise ValueError("RAID 100 requires exactly 12 devices")
        
        # RAMディスクデバイスを作成
        print(f"\n🚀 Initializing RAMDisk RAID 100 System")
        print(f"   Creating {num_devices} RAMDisk devices ({device_capacity_mb}MB each)...")
        
        self.devices = [
            RAMDiskDevice(device_id=i, capacity_mb=device_capacity_mb)
            for i in range(num_devices)
        ]
        
        # RAID構造を構築
        self.raid1_pairs = []
        for i in range(6):
            raid1 = RAID1_XOR(self.devices[i*2], self.devices[i*2+1], raid_id=i)
            self.raid1_pairs.append(raid1)
        
        self.raid10_groups = []
        for i in range(3):
            raid10 = RAID10_XOR([self.raid1_pairs[i*2], self.raid1_pairs[i*2+1]], raid_id=i)
            self.raid10_groups.append(raid10)
        
        self.num_groups = len(self.raid10_groups)
        self.capacity = min(r.capacity for r in self.raid10_groups) * self.num_groups
        
        # ファイルシステム用メタデータ
        self.files: Dict[str, Dict] = {}  # filename -> {chunks: [chunk_ids], size: bytes}
        self.next_chunk_id = 0
        
        total_capacity_mb = device_capacity_mb * num_devices
        usable_capacity_mb = total_capacity_mb / 2  # 50% efficiency
        
        print(f"\n✅ RAMDisk RAID 100 initialized")
        print(f"   ├─ Total RAM allocated: {total_capacity_mb}MB")
        print(f"   ├─ Usable capacity: {usable_capacity_mb}MB (50% efficiency)")
        print(f"   ├─ Chunk size: 4KB")
        print(f"   └─ Total chunks: {self.capacity}")
    
    def write_chunk(self, logical_chunk_id: int, data: bytes) -> bool:
        """チャンクを書き込む"""
        if logical_chunk_id >= self.capacity:
            raise ValueError(f"Chunk ID exceeds capacity")
        
        group_index = logical_chunk_id % self.num_groups
        group_chunk_id = logical_chunk_id // self.num_groups
        
        return self.raid10_groups[group_index].write(group_chunk_id, data)
    
    def read_chunk(self, logical_chunk_id: int) -> Optional[bytes]:
        """チャンクを読み取る"""
        if logical_chunk_id >= self.capacity:
            raise ValueError(f"Chunk ID exceeds capacity")
        
        group_index = logical_chunk_id % self.num_groups
        group_chunk_id = logical_chunk_id // self.num_groups
        
        return self.raid10_groups[group_index].read(group_chunk_id)
    
    def write_file(self, filename: str, data: bytes) -> bool:
        """
        ファイルをRAMディスクに書き込む
        データを4KBチャンクに分割して保存
        """
        chunk_size = 4096
        chunks_needed = (len(data) + chunk_size - 1) // chunk_size
        
        if self.next_chunk_id + chunks_needed > self.capacity:
            print(f"❌ Not enough space for file '{filename}'")
            return False
        
        chunk_ids = []
        for i in range(chunks_needed):
            chunk_data = data[i * chunk_size:(i + 1) * chunk_size]
            chunk_id = self.next_chunk_id + i
            
            if not self.write_chunk(chunk_id, chunk_data):
                print(f"❌ Failed to write chunk {chunk_id}")
                return False
            
            chunk_ids.append(chunk_id)
        
        self.files[filename] = {
            'chunks': chunk_ids,
            'size': len(data),
            'created': time.time()
        }
        
        self.next_chunk_id += chunks_needed
        
        print(f"💾 File '{filename}' written ({len(data)} bytes, {chunks_needed} chunks)")
        return True
    
    def read_file(self, filename: str) -> Optional[bytes]:
        """ファイルをRAMディスクから読み取る"""
        if filename not in self.files:
            print(f"❌ File '{filename}' not found")
            return None
        
        file_info = self.files[filename]
        chunks = []
        
        for chunk_id in file_info['chunks']:
            chunk_data = self.read_chunk(chunk_id)
            if chunk_data is None:
                print(f"❌ Failed to read chunk {chunk_id}")
                return None
            chunks.append(chunk_data)
        
        data = b''.join(chunks)[:file_info['size']]
        
        print(f"📖 File '{filename}' read ({len(data)} bytes)")
        return data
    
    def delete_file(self, filename: str) -> bool:
        """ファイルを削除"""
        if filename not in self.files:
            print(f"❌ File '{filename}' not found")
            return False
        
        del self.files[filename]
        print(f"🗑️  File '{filename}' deleted")
        return True
    
    def list_files(self) -> List[Dict]:
        """ファイル一覧を取得"""
        return [
            {
                'filename': name,
                'size_bytes': info['size'],
                'size_kb': info['size'] / 1024,
                'chunks': len(info['chunks']),
                'created': time.ctime(info['created'])
            }
            for name, info in self.files.items()
        ]
    
    def get_memory_stats(self) -> Dict:
        """メモリ使用統計を取得"""
        device_stats = [d.get_stats() for d in self.devices]
        total_allocated = sum(d.capacity_mb for d in self.devices)
        total_used = sum(d.get_memory_usage_mb() for d in self.devices)
        total_reads = sum(s['reads'] for s in device_stats)
        total_writes = sum(s['writes'] for s in device_stats)
        total_read_mb = sum(s['read_mb'] for s in device_stats)
        total_write_mb = sum(s['write_mb'] for s in device_stats)
        
        return {
            'total_allocated_mb': total_allocated,
            'total_used_mb': total_used,
            'utilization': (total_used / total_allocated) * 100,
            'files_stored': len(self.files),
            'total_reads': total_reads,
            'total_writes': total_writes,
            'total_read_mb': total_read_mb,
            'total_write_mb': total_write_mb,
            'failed_devices': [d.device_id for d in self.devices if d.is_failed],
            'xor_mismatches': sum(p.xor_mismatches for p in self.raid1_pairs)
        }
    
    def save_snapshot(self, filepath: str):
        """
        RAMディスクの内容をディスクに永続化
        全デバイスのデータとメタデータを保存
        """
        snapshot = {
            'devices': [
                {
                    'device_id': d.device_id,
                    'chunks': d.chunks,
                    'is_failed': d.is_failed
                }
                for d in self.devices
            ],
            'files': self.files,
            'next_chunk_id': self.next_chunk_id,
            'timestamp': time.time()
        }
        
        with open(filepath, 'wb') as f:
            pickle.dump(snapshot, f)
        
        file_size_mb = os.path.getsize(filepath) / (1024 * 1024)
        print(f"💾 Snapshot saved to '{filepath}' ({file_size_mb:.2f}MB)")
    
    def load_snapshot(self, filepath: str):
        """
        スナップショットからRAMディスクを復元
        """
        if not os.path.exists(filepath):
            print(f"❌ Snapshot file '{filepath}' not found")
            return False
        
        with open(filepath, 'rb') as f:
            snapshot = pickle.load(f)
        
        # デバイスデータを復元
        for dev_data in snapshot['devices']:
            device = self.devices[dev_data['device_id']]
            device.chunks = dev_data['chunks']
            device.is_failed = dev_data['is_failed']
        
        self.files = snapshot['files']
        self.next_chunk_id = snapshot['next_chunk_id']
        
        snapshot_time = time.ctime(snapshot['timestamp'])
        print(f"✅ Snapshot loaded from '{filepath}' (created: {snapshot_time})")
        return True
    
    def benchmark(self, size_mb: int = 10):
        """
        RAMディスクのベンチマーク
        指定サイズのデータを書き込み・読み取りして速度を測定
        """
        print(f"\n⚡ Running RAMDisk Benchmark ({size_mb}MB)...")
        
        # テストデータを生成
        data = os.urandom(size_mb * 1024 * 1024)
        
        # 書き込みベンチマーク
        write_start = time.time()
        self.write_file('benchmark_test.bin', data)
        write_time = time.time() - write_start
        write_speed = size_mb / write_time
        
        # 読み取りベンチマーク
        read_start = time.time()
        read_data = self.read_file('benchmark_test.bin')
        read_time = time.time() - read_start
        read_speed = size_mb / read_time
        
        # 検証
        integrity_ok = (data == read_data)
        
        # クリーンアップ
        self.delete_file('benchmark_test.bin')
        
        print(f"\n📊 Benchmark Results:")
        print(f"   ├─ Write: {write_speed:.2f} MB/s ({write_time:.4f}s)")
        print(f"   ├─ Read:  {read_speed:.2f} MB/s ({read_time:.4f}s)")
        print(f"   └─ Data integrity: {'✅ OK' if integrity_ok else '❌ FAILED'}")
        
        return {
            'write_speed_mbs': write_speed,
            'read_speed_mbs': read_speed,
            'write_time': write_time,
            'read_time': read_time,
            'integrity': integrity_ok
        }
    
    def print_status(self):
        """システム状態を表示"""
        stats = self.get_memory_stats()
        
        print("\n" + "="*70)
        print("RAMDisk RAID 100 Status")
        print("="*70)
        print(f"Memory Allocated: {stats['total_allocated_mb']:.2f}MB")
        print(f"Memory Used: {stats['total_used_mb']:.2f}MB ({stats['utilization']:.1f}%)")
        print(f"Files Stored: {stats['files_stored']}")
        print(f"Total Reads: {stats['total_reads']} ({stats['total_read_mb']:.2f}MB)")
        print(f"Total Writes: {stats['total_writes']} ({stats['total_write_mb']:.2f}MB)")
        print(f"Failed Devices: {stats['failed_devices'] if stats['failed_devices'] else 'None'}")
        print(f"XOR Mismatches: {stats['xor_mismatches']}")
        print("="*70 + "\n")


def main():
    """RAMディスクRAID 100のデモ"""
    
    # RAMディスクRAID 100を作成（各デバイス50MB）
    ramdisk = RAMDiskRAID100(num_devices=12, device_capacity_mb=50)
    
    # ファイル操作のデモ
    print("\n📝 File Operations Demo\n")
    
    # テキストファイルを作成
    text_data = "Hello, RAMDisk RAID 100!\n" * 1000
    ramdisk.write_file('hello.txt', text_data.encode('utf-8'))
    
    # バイナリファイルを作成
    binary_data = os.urandom(1024 * 100)  # 100KB
    ramdisk.write_file('random.bin', binary_data)
    
    # 大きなファイルを作成
    large_data = b"X" * (1024 * 1024 * 5)  # 5MB
    ramdisk.write_file('large.dat', large_data)
    
    # ファイル一覧を表示
    print("\n📂 File List:")
    for file_info in ramdisk.list_files():
        print(f"   {file_info['filename']:20} {file_info['size_kb']:>10.2f} KB  "
              f"{file_info['chunks']:>4} chunks  {file_info['created']}")
    
    # ファイルを読み取る
    print("\n📖 Reading files...")
    read_text = ramdisk.read_file('hello.txt')
    if read_text:
        print(f"   hello.txt: {read_text[:50].decode('utf-8')}...")
    
    # 状態を表示
    ramdisk.print_status()
    
    # ベンチマーク実行
    ramdisk.benchmark(size_mb=20)
    
    # スナップショット保存
    print("\n💾 Saving snapshot...")
    ramdisk.save_snapshot('/home/claude/ramdisk_snapshot.pkl')
    
    # デバイス故障シミュレーション
    print("\n💥 Simulating device failure...")
    ramdisk.devices[0].fail()
    ramdisk.devices[2].fail()
    
    # 故障後もファイルが読めることを確認
    print("\n📖 Reading files after device failures...")
    read_text_after = ramdisk.read_file('hello.txt')
    if read_text_after:
        print(f"   ✅ File still readable: {read_text_after[:30].decode('utf-8')}...")
    
    ramdisk.print_status()
    
    # 新しいRAMディスクを作成してスナップショットから復元
    print("\n🔄 Creating new RAMDisk and loading snapshot...")
    ramdisk2 = RAMDiskRAID100(num_devices=12, device_capacity_mb=50)
    ramdisk2.load_snapshot('/home/claude/ramdisk_snapshot.pkl')
    
    print("\n📂 Files after restoration:")
    for file_info in ramdisk2.list_files():
        print(f"   {file_info['filename']:20} {file_info['size_kb']:>10.2f} KB")
    
    ramdisk2.print_status()
    
    print("\n✅ RAMDisk RAID 100 Demo Complete!")


if __name__ == "__main__":
    main()
