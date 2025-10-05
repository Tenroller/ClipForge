#!/usr/bin/env python3
"""
Compilation Process Monitor
Monitors the video compilation process and provides real-time feedback
"""

import os
import time
import psutil
import json
from pathlib import Path

def monitor_compilation_process():
    """Monitor the compilation process and report status"""
    
    # Look for video processor processes
    video_processes = []
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if 'python' in proc.info['name'].lower():
                cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
                if any(keyword in cmdline.lower() for keyword in ['compilation', 'generator', 'video-processor']):
                    video_processes.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    
    print("🔍 Video Compilation Process Monitor")
    print("="*50)
    
    if not video_processes:
        print("❌ No video compilation processes found")
        return
    
    print(f"✅ Found {len(video_processes)} video processing processes")
    
    for proc in video_processes:
        try:
            info = proc.info
            print(f"\n📊 Process {info['pid']}:")
            print(f"   Command: {' '.join(info['cmdline'][:3])}")
            
            # Get process stats
            with proc.oneshot():
                cpu_percent = proc.cpu_percent()
                memory_info = proc.memory_info()
                memory_mb = memory_info.rss / (1024 * 1024)
                
                print(f"   CPU Usage: {cpu_percent:.1f}%")
                print(f"   Memory Usage: {memory_mb:.1f} MB")
                
                # Check if process is responsive
                try:
                    status = proc.status()
                    print(f"   Status: {status}")
                    
                    if status == 'sleeping':
                        print("   💤 Process is sleeping (might be waiting for I/O)")
                    elif status == 'running':
                        print("   🏃 Process is actively running")
                    elif status == 'disk-sleep':
                        print("   💾 Process is waiting for disk I/O")
                    
                except:
                    pass
                    
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            print(f"   ❌ Error accessing process: {e}")
    
    # Check temp directories for activity
    print(f"\n📁 Checking temporary directories...")
    temp_dirs = [
        "temp_vertical",
        "output", 
        "/tmp",
        "vendors/temp"
    ]
    
    for temp_dir in temp_dirs:
        if os.path.exists(temp_dir):
            try:
                # Get recent files (modified in last 5 minutes)
                recent_files = []
                cutoff_time = time.time() - 300  # 5 minutes ago
                
                for root, dirs, files in os.walk(temp_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        try:
                            mtime = os.path.getmtime(file_path)
                            if mtime > cutoff_time:
                                size = os.path.getsize(file_path)
                                recent_files.append((file_path, mtime, size))
                        except:
                            continue
                
                if recent_files:
                    print(f"   📂 {temp_dir}: {len(recent_files)} recent files")
                    # Show the most recent file
                    recent_files.sort(key=lambda x: x[1], reverse=True)
                    latest = recent_files[0]
                    print(f"      📄 Latest: {os.path.basename(latest[0])} ({latest[2]/1024/1024:.1f} MB)")
                else:
                    print(f"   📂 {temp_dir}: No recent activity")
            except Exception as e:
                print(f"   ❌ Error checking {temp_dir}: {e}")
    
    # System resource check
    print(f"\n💻 System Resources:")
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('.')
    
    print(f"   Memory: {memory.percent:.1f}% used ({memory.available/1024/1024/1024:.1f} GB available)")
    print(f"   Disk: {disk.percent:.1f}% used ({disk.free/1024/1024/1024:.1f} GB available)")
    
    # GPU check if available
    try:
        import GPUtil
        gpus = GPUtil.getGPUs()
        if gpus:
            print(f"   GPU Resources:")
            for gpu in gpus:
                print(f"      GPU {gpu.id}: {gpu.memoryUtil*100:.1f}% memory used")
    except ImportError:
        pass

def check_for_hanging_process():
    """Check if processes are hanging based on activity patterns"""
    print(f"\n🕵️ Checking for hanging processes...")
    
    # Look for processes with high CPU but no recent file activity
    hanging_indicators = []
    
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'create_time']):
        try:
            if 'python' in proc.info['name'].lower():
                cpu_percent = proc.cpu_percent(interval=1)
                age_minutes = (time.time() - proc.info['create_time']) / 60
                
                # Check if process has been running for a while with low CPU
                if age_minutes > 10 and cpu_percent < 5:  # Running >10min with <5% CPU
                    hanging_indicators.append({
                        'pid': proc.info['pid'],
                        'age_minutes': age_minutes,
                        'cpu_percent': cpu_percent
                    })
        except:
            continue
    
    if hanging_indicators:
        print(f"⚠️  Found {len(hanging_indicators)} potentially hanging processes:")
        for indicator in hanging_indicators:
            print(f"   PID {indicator['pid']}: Running {indicator['age_minutes']:.1f}min, CPU: {indicator['cpu_percent']:.1f}%")
        
        print(f"\n💡 Recommendations:")
        print(f"   • Check if these processes are stuck")
        print(f"   • Consider restarting if no progress for >30min")
        print(f"   • Monitor system logs for errors")
    else:
        print("✅ No obviously hanging processes detected")

if __name__ == "__main__":
    try:
        while True:
            monitor_compilation_process()
            check_for_hanging_process()
            print(f"\n" + "="*50)
            print(f"⏰ Monitor update: {time.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"🔄 Refreshing in 30 seconds... (Ctrl+C to exit)")
            time.sleep(30)
            
    except KeyboardInterrupt:
        print(f"\n👋 Monitor stopped by user")
    except Exception as e:
        print(f"❌ Monitor error: {e}")