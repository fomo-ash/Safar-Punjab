import React, { useState, useEffect, useRef } from 'react';
import { StyleSheet, View, Text } from 'react-native';
import MapView, { Marker, Polyline } from 'react-native-maps';
import { Stack, useLocalSearchParams } from 'expo-router';

const API_URL = process.env.EXPO_PUBLIC_API_URL || '';
const WS_URL = API_URL.replace('http://', 'ws://');

const INITIAL_REGION = {
  latitude: 31.6340, // Centered on Amritsar, Punjab
  longitude: 74.8723,
  latitudeDelta: 0.0922,
  longitudeDelta: 0.0421,
};

export default function TrackScreen() {
  // --- THIS IS THE FIX ---
  // We get all params and look for the correct one.
  // The search screen sends 'busNo' but our main screen sends 'busId'.
  // This code handles both, preferring 'busId' if it exists.
  const params = useLocalSearchParams<{ busId?: string, busNo?: string }>();
  const routeId = params.busId || params.busNo; 

  const [busLocation, setBusLocation] = useState<{ latitude: number; longitude: number } | null>(null);
  const [connectionStatus, setConnectionStatus] = useState('Initializing...');
  const websocket = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!routeId || !WS_URL) {
      setConnectionStatus(`Error: Invalid Route ID or API URL.`);
      return;
    }

    const ws = new WebSocket(`${WS_URL}/ws/track/${routeId}`);
    websocket.current = ws;
    setConnectionStatus('Connecting...');

    ws.onopen = () => { setConnectionStatus('Live'); };
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.lat && data.lon) {
          setBusLocation({ latitude: data.lat, longitude: data.lon });
        }
      } catch (e) { console.error('Failed to parse WebSocket message:', e); }
    };
    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      setConnectionStatus('Connection Error');
    };
    ws.onclose = () => { setConnectionStatus('Disconnected'); };

    return () => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.close();
      }
    };
  }, [routeId]);

  return (
    <>
      <Stack.Screen options={{ title: `Tracking Route: ${routeId || '...'}` }} />
      <View style={styles.container}>
        <MapView style={styles.map} initialRegion={INITIAL_REGION}>
          {busLocation && (
            <Marker
              coordinate={busLocation}
              title={`Route ${routeId}`}
            />
          )}
        </MapView>
        <View style={styles.statusBar}>
            <Text style={styles.statusText}>Status: {connectionStatus}</Text>
        </View>
      </View>
    </>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, },
  map: { width: '100%', height: '100%', },
  statusBar: { position: 'absolute', top: 0, left: 0, right: 0, backgroundColor: 'rgba(255, 255, 255, 0.8)', padding: 10, alignItems: 'center', },
  statusText: { fontWeight: 'bold', },
});
