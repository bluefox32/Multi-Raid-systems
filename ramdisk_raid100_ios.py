#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RAMDisk RAID 100 for iOS Pythonista
iOS環境で動作するRAMディスクRAIDシステム

Pythonista 3対応:
- iOS標準ライブラリのみ使用
- タッチ操作対応のUI（オプション）
- メモリ効率を最適化
"""

import os
import pickle
import time
from typing import List, Optional, Dict, Tuple
from dataclasses import dataclass, field
import json

# Pythonistaのuiモジュールをインポート（利用可能な場合）
try:
    import ui
    import console
    PYTHONISTA_UI_AVAILABLE = True
except ImportError:
    PYTHONISTA_UI_AVAILABLE = False
    print("⚠️  Running without Pythonista UI (console mode)")


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
    RAMディスクデバイス（iOS最適化版）
    メモリ効率を重視した実装
    """
    device_id: int
    capacity_mb: int
    chunk_size: int = 4096
    
    chunks: Dict[int, bytes] = field(default_factory=dict)
    is_failed: bool = False
    read_count: int = 0
    write_count: int = 0
    read_bytes: int = 0
    write_bytes: int = 0
    
    def __post_init__(self):
        """初期化"""
        self.max_chunks = (self.capacity_mb * 1024 * 1024) // self.chunk_size
    
    def write_chunk(self, chunk_id: int, data: bytes) -> bool:
        """チャンク書き込み"""
        if self.is_failed:
            return False
        if chunk_id >= self.max_chunks:
            raise ValueError(f"Chunk ID {chunk_id} exceeds capacity")
        
        if len(data) > self.chunk_size:
            data = data[:self.chunk_size]
        
        self.chunks[chunk_id] = data
        self.write_count += 1
        self.write_bytes += len(data)
        return True
    
    def read_chunk(self, chunk_id: int) -> Optional[bytes]:
        """チャンク読み取り"""
        if self.is_failed:
            return None
        
        self.read_count += 1
        data = self.chunks.get(chunk_id)
        if data:
            self.read_bytes += len(data)
        return data
    
    def get_memory_usage(self) -> int:
        """メモリ使用量（バイト）"""
        return sum(len(data) for data in self.chunks.values())
    
    def get_memory_usage_mb(self) -> float:
        """メモリ使用量（MB）"""
        return self.get_memory_usage() / (1024 * 1024)
    
    def fail(self):
        """故障"""
        self.is_failed = True
    
    def recover(self):
        """復旧"""
        self.is_failed = False
    
    def clear(self):
        """クリア"""
        self.chunks.clear()
        self.read_count = 0
        self.write_count = 0
        self.read_bytes = 0
        self.write_bytes = 0


class RAID1_XOR:
    """RAID 1 with XOR"""
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
            return data1
        
        return data1
    
    def is_operational(self) -> bool:
        return not (self.device1.is_failed and self.device2.is_failed)


class RAID10_XOR:
    """RAID 10 with XOR"""
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
    RAMディスクRAID 100（iOS Pythonista版）
    """
    def __init__(self, num_devices: int = 12, device_capacity_mb: int = 20):
        """
        初期化（iOS向けに容量を控えめに設定）
        
        Args:
            num_devices: デバイス数（12固定）
            device_capacity_mb: 各デバイスの容量（デフォルト20MB、iOSメモリ制限考慮）
        """
        if num_devices != 12:
            raise ValueError("RAID 100 requires exactly 12 devices")
        
        print("🚀 RAMDisk RAID 100 (iOS版)")
        print(f"   デバイス: {num_devices}台 × {device_capacity_mb}MB")
        
        # RAMディスクデバイス作成
        self.devices = [
            RAMDiskDevice(device_id=i, capacity_mb=device_capacity_mb)
            for i in range(num_devices)
        ]
        
        # RAID構造構築
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
        
        # ファイルシステム
        self.files: Dict[str, Dict] = {}
        self.next_chunk_id = 0
        
        total_mb = device_capacity_mb * num_devices
        usable_mb = total_mb / 2
        
        print(f"✅ 初期化完了")
        print(f"   総容量: {total_mb}MB → 使用可能: {usable_mb}MB")
    
    def write_chunk(self, logical_chunk_id: int, data: bytes) -> bool:
        """チャンク書き込み"""
        if logical_chunk_id >= self.capacity:
            raise ValueError("容量超過")
        
        group_index = logical_chunk_id % self.num_groups
        group_chunk_id = logical_chunk_id // self.num_groups
        
        return self.raid10_groups[group_index].write(group_chunk_id, data)
    
    def read_chunk(self, logical_chunk_id: int) -> Optional[bytes]:
        """チャンク読み取り"""
        if logical_chunk_id >= self.capacity:
            raise ValueError("容量超過")
        
        group_index = logical_chunk_id % self.num_groups
        group_chunk_id = logical_chunk_id // self.num_groups
        
        return self.raid10_groups[group_index].read(group_chunk_id)
    
    def write_file(self, filename: str, data: bytes) -> bool:
        """ファイル書き込み"""
        chunk_size = 4096
        chunks_needed = (len(data) + chunk_size - 1) // chunk_size
        
        if self.next_chunk_id + chunks_needed > self.capacity:
            print(f"❌ 容量不足: {filename}")
            return False
        
        chunk_ids = []
        for i in range(chunks_needed):
            chunk_data = data[i * chunk_size:(i + 1) * chunk_size]
            chunk_id = self.next_chunk_id + i
            
            if not self.write_chunk(chunk_id, chunk_data):
                print(f"❌ 書き込み失敗: chunk {chunk_id}")
                return False
            
            chunk_ids.append(chunk_id)
        
        self.files[filename] = {
            'chunks': chunk_ids,
            'size': len(data),
            'created': time.time()
        }
        
        self.next_chunk_id += chunks_needed
        
        size_kb = len(data) / 1024
        print(f"💾 {filename} ({size_kb:.1f}KB, {chunks_needed}チャンク)")
        return True
    
    def read_file(self, filename: str) -> Optional[bytes]:
        """ファイル読み取り"""
        if filename not in self.files:
            print(f"❌ ファイルが見つかりません: {filename}")
            return None
        
        file_info = self.files[filename]
        chunks = []
        
        for chunk_id in file_info['chunks']:
            chunk_data = self.read_chunk(chunk_id)
            if chunk_data is None:
                print(f"❌ チャンク読み取り失敗: {chunk_id}")
                return None
            chunks.append(chunk_data)
        
        data = b''.join(chunks)[:file_info['size']]
        return data
    
    def delete_file(self, filename: str) -> bool:
        """ファイル削除"""
        if filename not in self.files:
            return False
        del self.files[filename]
        print(f"🗑️  削除: {filename}")
        return True
    
    def list_files(self) -> List[Dict]:
        """ファイル一覧"""
        return [
            {
                'filename': name,
                'size_bytes': info['size'],
                'size_kb': info['size'] / 1024,
                'chunks': len(info['chunks'])
            }
            for name, info in self.files.items()
        ]
    
    def get_stats(self) -> Dict:
        """統計情報"""
        total_allocated = sum(d.capacity_mb for d in self.devices)
        total_used = sum(d.get_memory_usage_mb() for d in self.devices)
        
        return {
            'allocated_mb': total_allocated,
            'used_mb': total_used,
            'utilization': (total_used / total_allocated) * 100 if total_allocated > 0 else 0,
            'files': len(self.files),
            'failed_devices': [d.device_id for d in self.devices if d.is_failed]
        }
    
    def save_snapshot(self, filepath: str):
        """スナップショット保存"""
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
        
        file_size = os.path.getsize(filepath) / (1024 * 1024)
        print(f"💾 スナップショット保存: {filepath} ({file_size:.2f}MB)")
    
    def load_snapshot(self, filepath: str):
        """スナップショット読み込み"""
        if not os.path.exists(filepath):
            print(f"❌ ファイルが見つかりません: {filepath}")
            return False
        
        with open(filepath, 'rb') as f:
            snapshot = pickle.load(f)
        
        for dev_data in snapshot['devices']:
            device = self.devices[dev_data['device_id']]
            device.chunks = dev_data['chunks']
            device.is_failed = dev_data['is_failed']
        
        self.files = snapshot['files']
        self.next_chunk_id = snapshot['next_chunk_id']
        
        print(f"✅ スナップショット読み込み完了")
        return True
    
    def print_status(self):
        """状態表示"""
        stats = self.get_stats()
        
        print("\n" + "="*50)
        print("📊 RAMDisk RAID 100 ステータス")
        print("="*50)
        print(f"割当: {stats['allocated_mb']:.1f}MB")
        print(f"使用: {stats['used_mb']:.2f}MB ({stats['utilization']:.1f}%)")
        print(f"ファイル数: {stats['files']}")
        print(f"故障デバイス: {stats['failed_devices'] if stats['failed_devices'] else 'なし'}")
        print("="*50 + "\n")


def demo_simple():
    """シンプルなデモ（iOS向け）"""
    print("\n🎯 RAMDisk RAID 100 デモ（iOS版）\n")
    
    # 小容量で作成（iOSメモリ制限考慮）
    ramdisk = RAMDiskRAID100(num_devices=12, device_capacity_mb=10)
    
    # テキストファイル作成
    print("\n📝 ファイル作成テスト")
    text1 = "こんにちは、RAMディスクRAID 100！\n" * 100
    ramdisk.write_file('test.txt', text1.encode('utf-8'))
    
    # バイナリファイル作成
    binary_data = os.urandom(1024 * 50)  # 50KB
    ramdisk.write_file('data.bin', binary_data)
    
    # ファイル一覧
    print("\n📂 ファイル一覧:")
    for f in ramdisk.list_files():
        print(f"   {f['filename']:15} {f['size_kb']:>8.2f}KB")
    
    # 読み取りテスト
    print("\n📖 読み取りテスト")
    read_text = ramdisk.read_file('test.txt')
    if read_text:
        preview = read_text[:50].decode('utf-8', errors='ignore')
        print(f"   {preview}...")
    
    # 状態表示
    ramdisk.print_status()
    
    # 故障シミュレーション
    print("💥 デバイス故障シミュレーション")
    ramdisk.devices[0].fail()
    print("   Device 0 故障")
    
    # 故障後の読み取り
    print("\n📖 故障後の読み取りテスト")
    read_text2 = ramdisk.read_file('test.txt')
    if read_text2:
        print("   ✅ ファイルは正常に読み取れました")
    
    ramdisk.print_status()
    
    # スナップショット保存（Pythonistaのドキュメントフォルダに保存）
    # iOS Pythonistaでは ~/Documents/ を使用
    # 通常のPythonでは /tmp/ または現在のディレクトリを使用
    try:
        snapshot_path = os.path.expanduser('~/Documents/ramdisk_snapshot.pkl')
        os.makedirs(os.path.dirname(snapshot_path), exist_ok=True)
    except:
        snapshot_path = '/tmp/ramdisk_snapshot.pkl'
    
    print(f"\n💾 スナップショット保存")
    ramdisk.save_snapshot(snapshot_path)
    
    print("\n✅ デモ完了！")
    return ramdisk


def interactive_menu(ramdisk: RAMDiskRAID100):
    """インタラクティブメニュー（コンソール版）"""
    while True:
        print("\n" + "="*50)
        print("RAMDisk RAID 100 メニュー")
        print("="*50)
        print("1. ファイル作成")
        print("2. ファイル読み取り")
        print("3. ファイル一覧")
        print("4. ファイル削除")
        print("5. ステータス表示")
        print("6. デバイス故障シミュレーション")
        print("7. スナップショット保存")
        print("8. スナップショット読み込み")
        print("0. 終了")
        print("="*50)
        
        try:
            choice = input("\n選択: ").strip()
            
            if choice == '0':
                print("👋 終了します")
                break
            elif choice == '1':
                filename = input("ファイル名: ").strip()
                content = input("内容: ").strip()
                ramdisk.write_file(filename, content.encode('utf-8'))
            elif choice == '2':
                filename = input("ファイル名: ").strip()
                data = ramdisk.read_file(filename)
                if data:
                    print(f"\n📄 内容:\n{data.decode('utf-8', errors='ignore')}")
            elif choice == '3':
                print("\n📂 ファイル一覧:")
                for f in ramdisk.list_files():
                    print(f"   {f['filename']:20} {f['size_kb']:>8.2f}KB")
            elif choice == '4':
                filename = input("ファイル名: ").strip()
                ramdisk.delete_file(filename)
            elif choice == '5':
                ramdisk.print_status()
            elif choice == '6':
                device_id = int(input("故障させるデバイスID (0-11): ").strip())
                if 0 <= device_id < 12:
                    ramdisk.devices[device_id].fail()
                    print(f"⚠️  Device {device_id} を故障させました")
            elif choice == '7':
                path = input("保存先 (default: ~/Documents/snapshot.pkl): ").strip()
                if not path:
                    path = os.path.expanduser('~/Documents/ramdisk_snapshot.pkl')
                ramdisk.save_snapshot(path)
            elif choice == '8':
                path = input("読み込み元 (default: ~/Documents/snapshot.pkl): ").strip()
                if not path:
                    path = os.path.expanduser('~/Documents/ramdisk_snapshot.pkl')
                ramdisk.load_snapshot(path)
        except Exception as e:
            print(f"❌ エラー: {e}")


def main():
    """メイン関数"""
    if PYTHONISTA_UI_AVAILABLE:
        print("📱 Pythonista環境を検出")
        console.clear()
    
    print("="*50)
    print("RAMDisk RAID 100 for iOS Pythonista")
    print("="*50)
    
    # デモ実行
    ramdisk = demo_simple()
    
    # インタラクティブモード（オプション）
    print("\n" + "="*50)
    choice = input("インタラクティブモードを起動しますか？ (y/n): ").strip().lower()
    if choice == 'y':
        interactive_menu(ramdisk)


if __name__ == "__main__":
    main()
