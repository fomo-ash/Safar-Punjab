// frontend/app/start-trip.tsx
import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, FlatList, TouchableOpacity, Alert, Button } from 'react-native';
import { router, Stack } from 'expo-router';
import { useSession } from './hooks/useAuth'; 

const API_URL = process.env.EXPO_PUBLIC_API_URL;

interface Route {
  route_id: string;
  name: string;
}

export default function StartTripScreen() {
  const { session, signOut } = useSession();
  const [routes, setRoutes] = useState<Route[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    async function fetchRoutes() {
      if (!session) return;
      try {
        const response = await fetch(`${API_URL}/routes`);
        if (response.ok) {
          const data = await response.json();
          setRoutes(data);
        } else {
          Alert.alert('Error', 'Failed to fetch routes.');
        }
      } catch (e) {
        console.error(e);
        Alert.alert('Error', 'Could not connect to the server to fetch routes.');
      } finally {
        setIsLoading(false);
      }
    }
    fetchRoutes();
  }, [session]);

  const handleStartTrip = async (routeId: string) => {
    if (!session) {
      Alert.alert('Error', 'You are not logged in.');
      return;
    }

    try {
      const response = await fetch(`${API_URL}/trips/start`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${session}`, 
        },
        body: JSON.stringify({ route_id: routeId }),
      });

      if (response.ok) {
        Alert.alert('Success', `Trip started on route ${routeId}. Now navigating to live broadcast screen.`);
        router.push('/driver-live');
      } else {
        const errorData = await response.json();
        Alert.alert('Failed to Start Trip', errorData.detail || 'An unknown error occurred.');
      }
    } catch (e) {
      console.error(e);
      Alert.alert('Error', 'Could not connect to the server to start the trip.');
    }
  };

  if (isLoading) {
    return (
      <View style={styles.container}>
        <Text>Loading routes...</Text>
      </View>
    );
  }

  return (
    <>
      <Stack.Screen options={{ title: 'Select a Route', headerRight: () => <Button onPress={signOut} title="Logout" color="#d9534f"/> }} />
      <View style={styles.container}>
        <FlatList
          data={routes}
          keyExtractor={(item) => item.route_id}
          renderItem={({ item }) => (
            <TouchableOpacity style={styles.routeItem} onPress={() => handleStartTrip(item.route_id)}>
              <Text style={styles.routeId}>{item.route_id}</Text>
              <Text style={styles.routeName}>{item.name}</Text>
            </TouchableOpacity>
          )}
          ListHeaderComponent={<Text style={styles.header}>Tap a route to start your trip</Text>}
        />
      </View>
    </>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  header: {
    fontSize: 22,
    fontWeight: 'bold',
    textAlign: 'center',
    padding: 20,
  },
  routeItem: {
    backgroundColor: 'white',
    padding: 20,
    marginVertical: 8,
    marginHorizontal: 16,
    borderRadius: 8,
    elevation: 2,
  },
  routeId: {
    fontSize: 18,
    fontWeight: 'bold',
  },
  routeName: {
    fontSize: 14,
    color: 'gray',
  },
});