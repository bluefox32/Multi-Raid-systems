#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RAID 100 XOR System - 使用例集

このファイルはRAID 100 XOR Systemの様々な使用方法を示しています。
"""

# 例1: 基本的なRAID 100シミュレーター
def example1_basic_simulator():
    """例1: 基本的なRAID 100の使用"""
    from raid100_simulator import RAID100, StorageDevice
    
    print("=" * 50)
    print("例1: 基本的なRAID 100シミュレーター")
    print("=" * 50)
    
    # 12台のストレージデバイスを作成
    devices = [StorageDevice(device_id=i, capacity=100) for i in range(12)]
    
    # RAID 100を構築
    raid100 = RAID100(devices)
    
    # データを書き込み
    test_data = b"Hello, RAID 100!"
    raid100.write(0, test_data)
    print(f"✅ データを書き込み: {test_data}")
    
    # データを読み取り
    read_data = raid100.read(0)
    print(f"✅ データを読み取り: {read_data}")
    
    # デバイス故障をシミュレート
    devices[0].fail()
    print(f"⚠️  Device 0を故障させました")
    
    # データはまだ読み取り可能
    read_data_after = raid100.read(0)
    if read_data_after:
        print(f"✅ 故障後もデータは読み取り可能: {read_data_after}")
    
    raid100.print_status()


# 例2: XOR方式での実装
def example2_xor_parity():
    """例2: XORパリティ検証付きRAID 100"""
    from raid100_xor import RAID100_XOR, StorageDevice
    
    print("\n" + "=" * 50)
    print("例2: XORパリティ検証付きRAID 100")
    print("=" * 50)
    
    # 修正(2026-10-29): raid100_xor には RAMDiskDevice は無く（それは ramdisk_raid100 側の
    # クラス）、RAID100_XOR が受け取るのは raid100_xor 自身の StorageDevice のため差し替えた
    # ストレージデバイスを作成（100チャンクずつ）
    devices = [StorageDevice(device_id=i, capacity=100) for i in range(12)]
    
    # XOR検証付きで実装
    raid100_xor = RAID100_XOR(devices)
    
    # テストデータを作成
    data1 = b"XOR Test Data 1"
    data2 = b"XOR Test Data 2"
    
    # 書き込み
    raid100_xor.write(0, data1)
    raid100_xor.write(1, data2)
    print(f"✅ XOR検証付きで書き込み完了")
    
    # 読み取り
    read1 = raid100_xor.read(0)
    read2 = raid100_xor.read(1)
    print(f"✅ Chunk 0: {read1}")
    print(f"✅ Chunk 1: {read2}")
    
    # 統計情報を表示
    stats = raid100_xor.get_stats()
    print(f"📊 XOR不一致: {stats['xor_mismatches']}")


# 例3: RAMディスク版（推奨）
def example3_ramdisk():
    """例3: RAMディスク版の使用（最も推奨）"""
    from ramdisk_raid100 import RAMDiskRAID100
    
    print("\n" + "=" * 50)
    print("例3: RAMディスク版RAID 100")
    print("=" * 50)
    
    # RAMディスク RAID 100を作成
    ramdisk = RAMDiskRAID100(num_devices=12, device_capacity_mb=100)
    
    # テキストファイル作成
    text_content = b"Hello, RAMDisk RAID 100! This is a test file."
    ramdisk.write_file('document.txt', text_content)
    print(f"✅ document.txt を作成")
    
    # バイナリファイル作成
    binary_content = b'\x00\x01\x02\x03' * 256  # 1KB
    ramdisk.write_file('data.bin', binary_content)
    print(f"✅ data.bin を作成")
    
    # ファイル一覧表示
    print("\n📂 ファイル一覧:")
    for file_info in ramdisk.list_files():
        print(f"   {file_info['filename']:20} {file_info['size_kb']:>10.2f}KB")
    
    # ファイルを読み取る
    read_text = ramdisk.read_file('document.txt')
    print(f"\n📖 document.txt の内容:")
    print(f"   {read_text.decode('utf-8')}")
    
    # メモリ統計を表示
    ramdisk.print_status()
    
    # スナップショット保存
    ramdisk.save_snapshot('/tmp/raid100_snapshot.pkl')
    print(f"✅ スナップショット保存完了")


# 例4: ファイル操作の詳細
def example4_file_operations():
    """例4: ファイル操作の詳細な例"""
    from ramdisk_raid100 import RAMDiskRAID100
    
    print("\n" + "=" * 50)
    print("例4: ファイル操作の詳細")
    print("=" * 50)
    
    ramdisk = RAMDiskRAID100(num_devices=12, device_capacity_mb=50)
    
    # 複数のファイルを作成
    files = {
        'notes.txt': b'Important notes about RAID systems',
        'config.json': b'{"raid_level": 100, "devices": 12}',
        'image.dat': b'\x89PNG\r\n\x1a\n' + b'\x00' * 100,
    }
    
    print("📝 ファイルを作成中...")
    for filename, content in files.items():
        ramdisk.write_file(filename, content)
        print(f"   ✅ {filename} ({len(content)} bytes)")
    
    print("\n📂 作成されたファイル:")
    for file_info in ramdisk.list_files():
        print(f"   {file_info['filename']:20} {file_info['size_kb']:>8.2f}KB  "
              f"({file_info['chunks']}チャンク)")
    
    print("\n🔍 ファイル削除テスト:")
    ramdisk.delete_file('notes.txt')
    print(f"   ✅ notes.txt を削除")
    
    print("\n📂 削除後のファイル:")
    for file_info in ramdisk.list_files():
        print(f"   {file_info['filename']}")


# 例5: 故障シミュレーション
def example5_failure_simulation():
    """例5: デバイス故障と復旧のシミュレーション"""
    from ramdisk_raid100 import RAMDiskRAID100
    
    print("\n" + "=" * 50)
    print("例5: 故障シミュレーション")
    print("=" * 50)
    
    ramdisk = RAMDiskRAID100(num_devices=12, device_capacity_mb=30)
    
    # テストデータを作成
    print("📝 テストデータを作成...")
    data = b"Critical data that must be protected" * 100
    ramdisk.write_file('critical.dat', data)
    print(f"✅ critical.dat を作成 ({len(data)} bytes)")
    
    # 正常な状態で読み取り
    print("\n🔍 正常状態での読み取り:")
    read1 = ramdisk.read_file('critical.dat')
    if read1 == data:
        print("✅ データ完全一致")
    
    # デバイスを1台故障させる
    print("\n💥 Device 0を故障させます...")
    ramdisk.devices[0].fail()
    ramdisk.print_status()
    
    # 故障後も読み取り可能か確認
    print("🔍 故障後の読み取り:")
    read2 = ramdisk.read_file('critical.dat')
    if read2 == data:
        print("✅ ミラーリングにより依然データ読み取り可能")
    
    # 別のデバイスも故障させる（別のペア）
    print("\n💥 Device 4も故障させます（別のペア）...")
    ramdisk.devices[4].fail()
    ramdisk.print_status()
    
    # 複数故障後も読み取り可能か確認
    print("🔍 複数故障後の読み取り:")
    read3 = ramdisk.read_file('critical.dat')
    if read3 == data:
        print("✅ RAID 100の冗長性により依然読み取り可能")
    else:
        print("❌ データが失われました")


# 例6: iOS Pythonista向け最小限の例
def example6_ios_minimal():
    """例6: iOS Pythonista向けの最小実装例"""
    try:
        from ramdisk_raid100_ios import RAMDiskRAID100
        import os
        
        print("\n" + "=" * 50)
        print("例6: iOS Pythonista向け最小実装")
        print("=" * 50)
        
        # iOSメモリ制限を考慮した小容量設定
        ramdisk = RAMDiskRAID100(num_devices=12, device_capacity_mb=10)
        
        # シンプルなテキストファイル
        ramdisk.write_file('test.txt', b'Hello from iOS!')
        
        # 読み取り
        content = ramdisk.read_file('test.txt')
        print(f"📝 {content.decode('utf-8')}")
        
        # スナップショット保存（iOS Documentsフォルダ）
        snapshot_path = os.path.expanduser('~/Documents/ios_snapshot.pkl')
        os.makedirs(os.path.dirname(snapshot_path), exist_ok=True)
        ramdisk.save_snapshot(snapshot_path)
        print(f"✅ スナップショット保存: {snapshot_path}")
        
    except ImportError:
        print("⚠️  iOS環境ではないため、シミュレーション表示")
        print("iOS Pythonistaでの実行を推奨")


# 例7: ベンチマーク
def example7_benchmark():
    """例7: パフォーマンスベンチマーク"""
    from ramdisk_raid100 import RAMDiskRAID100
    
    print("\n" + "=" * 50)
    print("例7: パフォーマンスベンチマーク")
    print("=" * 50)
    
    ramdisk = RAMDiskRAID100(num_devices=12, device_capacity_mb=100)
    
    # ベンチマーク実行
    results = ramdisk.benchmark(size_mb=20)
    
    print(f"\n📊 ベンチマーク結果:")
    print(f"   書き込み速度: {results['write_speed_mbs']:.2f} MB/s")
    print(f"   読み取り速度: {results['read_speed_mbs']:.2f} MB/s")
    print(f"   データ整合性: {'✅ OK' if results['integrity'] else '❌ NG'}")


def main():
    """メイン関数 - すべての例を実行"""
    print("🚀 RAID 100 XOR System - 使用例集\n")
    
    examples = [
        ("基本的なシミュレーター", example1_basic_simulator),
        ("XORパリティ検証", example2_xor_parity),
        ("RAMディスク版（推奨）", example3_ramdisk),
        ("ファイル操作", example4_file_operations),
        ("故障シミュレーション", example5_failure_simulation),
        ("iOS Pythonista版", example6_ios_minimal),
        ("パフォーマンスベンチマーク", example7_benchmark),
    ]
    
    print("実行可能な例:")
    for i, (name, _) in enumerate(examples, 1):
        print(f"  {i}. {name}")
    
    try:
        choice = input("\n実行する例番号を入力 (1-7): ").strip()
        idx = int(choice) - 1
        
        if 0 <= idx < len(examples):
            name, func = examples[idx]
            print(f"\n実行: {name}\n")
            func()
        else:
            print("❌ 無効な入力です")
            
    except (ValueError, KeyboardInterrupt):
        print("\n❌ 入力エラー")


if __name__ == "__main__":
    main()
