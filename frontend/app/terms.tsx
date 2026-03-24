import { View, Text, ScrollView } from "react-native";
import React from "react";

export default function Terms() {
  return (
    <ScrollView style={{ flex: 1, backgroundColor: "#FCF5E3", padding: 20 }}>
      <Text style={{ fontSize: 28, fontWeight: "bold", color: "#045633", marginBottom: 10 }}>
        Terms and Conditions
      </Text>
      <Text style={{ fontSize: 16, color: "#555", lineHeight: 22 }}>
        Here you can write your terms and conditions...
      </Text>
    </ScrollView>
  );
}
