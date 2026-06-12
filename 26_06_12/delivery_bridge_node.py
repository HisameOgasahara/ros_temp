#!/usr/bin/env python3
"""
Delivery Bridge Node - 웹 UI와 로봇을 연결하는 브릿지

웹 앱(HTML)에서 WebSocket으로 주문을 받아 /move_request 토픽으로 발행하고,
로봇이 /move_finish 토픽으로 true를 보내면 웹 앱에 완료를 전달합니다.

토픽:
- 발행: /move_request (String): "방이름_물건_call" 또는 "방이름_물건_recall"
- 구독: /move_finish (Bool): true → 현재 작업 완료, 다음 주문 처리

사용법:
  ros2 run rtreebot delivery_bridge
  ros2 run rtreebot delivery_bridge --ros-args -p ws_port:=3000
"""

import rclpy
from rclpy.node import Node
from std_msgs.msg import String, Bool
import json
import asyncio
import websockets
import time
from threading import Thread


class DeliveryBridgeNode(Node):
    def __init__(self):
        super().__init__('delivery_bridge_node')
        
        # 파라미터
        self.declare_parameter('ws_host', '0.0.0.0')
        self.declare_parameter('ws_port', 3000)
        
        self.ws_host = self.get_parameter('ws_host').value
        self.ws_port = self.get_parameter('ws_port').value
        
        # 발행: 웹 → 로봇
        self.move_request_pub = self.create_publisher(String, '/move_request', 10)
        
        # 구독: 로봇 → 웹 (Bool 타입)
        self.move_finish_sub = self.create_subscription(
            Bool,
            '/move_finish',
            self.move_finish_callback,
            10
        )
        
        # WebSocket
        self.ws_clients = set()
        self.loop = None
        
        self.get_logger().info('=' * 50)
        self.get_logger().info('🌐 Delivery Bridge Node 시작')
        self.get_logger().info(f'📡 WebSocket: ws://{self.ws_host}:{self.ws_port}')
        self.get_logger().info('📤 발행: /move_request (String)')
        self.get_logger().info('📥 구독: /move_finish (Bool)')
        self.get_logger().info('')
        self.get_logger().info('💡 로봇에서 true 발행하면 다음 주문 처리')
        self.get_logger().info('   ros2 topic pub --once /move_finish std_msgs/Bool "data: true"')
        self.get_logger().info('=' * 50)
    
    def move_finish_callback(self, msg):
        """로봇 완료 신호 수신 → 웹에 전달"""
        self.get_logger().info(f'📥 /move_finish: {msg.data}')
        
        # true일 때만 처리
        if msg.data:
            self.get_logger().info('✅ 작업 완료 신호 수신')
            
            # WebSocket으로 전달
            ws_message = {
                'type': 'robot_update',
                'data': 'finish',
                'timestamp': int(time.time() * 1000)
            }
            
            if self.loop and self.ws_clients:
                asyncio.run_coroutine_threadsafe(
                    self.broadcast_to_clients(ws_message),
                    self.loop
                )
    
    async def broadcast_to_clients(self, data):
        """모든 클라이언트에게 전송"""
        if not self.ws_clients:
            return
        
        message = json.dumps(data, ensure_ascii=False)
        disconnected = set()
        
        for client in self.ws_clients:
            try:
                await client.send(message)
            except:
                disconnected.add(client)
        
        self.ws_clients -= disconnected
    
    async def handle_client(self, websocket):
        """WebSocket 클라이언트 처리"""
        self.ws_clients.add(websocket)
        self.get_logger().info(f'🔌 클라이언트 연결: {websocket.remote_address}')
        
        try:
            async for message in websocket:
                await self.process_message(websocket, message)
        except websockets.exceptions.ConnectionClosed:
            self.get_logger().info(f'🔌 클라이언트 연결 해제')
        finally:
            self.ws_clients.discard(websocket)
    
    async def process_message(self, websocket, message):
        """WebSocket 메시지 처리"""
        try:
            data = json.loads(message)
            msg_type = data.get('type') or data.get('action')
            
            self.get_logger().info(f'📨 웹: {msg_type}')
            
            if msg_type == 'create_order':
                # 배송: "방이름_물건_call"
                destination = data.get('destination', 'A')
                item = data.get('item', 'unknown')
                command = f"{destination}_{item}_call"
                
                msg = String()
                msg.data = command
                self.move_request_pub.publish(msg)
                
                self.get_logger().info(f'📤 /move_request: {command}')
                
                await websocket.send(json.dumps({
                    'type': 'order_created',
                    'success': True,
                    'command': command
                }))
                
            elif msg_type == 'retrieve_item':
                # 회수: "방이름_물건_recall"
                destination = data.get('destination', 'A')
                item = data.get('item', 'unknown')
                command = f"{destination}_{item}_recall"
                
                msg = String()
                msg.data = command
                self.move_request_pub.publish(msg)
                
                self.get_logger().info(f'📤 /move_request: {command}')
                
                await websocket.send(json.dumps({
                    'type': 'retrieve_created',
                    'success': True,
                    'command': command
                }))
                
        except Exception as e:
            self.get_logger().error(f'❌ 오류: {e}')
    
    async def start_websocket_server(self):
        """WebSocket 서버 시작"""
        self.loop = asyncio.get_event_loop()
        
        async with websockets.serve(self.handle_client, self.ws_host, self.ws_port):
            self.get_logger().info(f'✅ WebSocket 서버 시작')
            await asyncio.Future()


def main(args=None):
    rclpy.init(args=args)
    node = DeliveryBridgeNode()
    
    # ROS2 스핀 (별도 스레드)
    ros_thread = Thread(target=lambda: rclpy.spin(node), daemon=True)
    ros_thread.start()
    
    # WebSocket 서버 (메인 스레드)
    try:
        asyncio.run(node.start_websocket_server())
    except KeyboardInterrupt:
        node.get_logger().info('🛑 종료')
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
