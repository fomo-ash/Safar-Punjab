import React, { useState } from "react";
import {
  View,
  Text,
  TouchableOpacity,
  Linking,
  StyleSheet,
} from "react-native";
import { Ionicons, FontAwesome } from "@expo/vector-icons";
import Footer from "@/components/footer";
import { useRouter } from "expo-router";

export default function More() {
  const [rating, setRating] = useState(0);
  const router = useRouter();

  const menuItems = [
    { label: "Change City", screen: "/changecity", active: true },
    { label: "Stops and Stations", screen: "/welcome", active: true }, 
    { label: "Language", screen: "/language", active: true },
    { label: "Terms and Conditions", screen: "/terms", active: true },
    { label: "My Grievances", screen: "/grievances", active: true },
    { label: "Contact Us", screen: "/contact", active: true },
  ];

  return (
    <View style={styles.container}>
      <View style={styles.innerContainer}>
        {menuItems.map((item, index) => (
          <TouchableOpacity
            key={index}
            disabled={!item.active}
            onPress={() => item.active && router.push(item.screen as any)}
            style={[
              styles.menuItem,
              {
                borderColor: item.active ? "#FFEAB4" : "#ddd",
                backgroundColor: item.active ? "#FFFBF2" : "#f2f2f2",
                opacity: item.active ? 1 : 0.6,
              },
            ]}
          >
            <Text
              style={{
                fontSize: 20,
                color: item.active ? "#EEAC09" : "#888",
              }}
            >
              {item.label}
            </Text>
            <Ionicons
              name="chevron-forward"
              size={20}
              color={item.active ? "#666" : "#aaa"}
            />
          </TouchableOpacity>
        ))}

        <Text style={styles.sectionTitle}>Follow us on</Text>
        <View style={styles.socialRow}>
          {[
            { icon: "twitter", url: "https://twitter.com" },
            { icon: "facebook", url: "https://facebook.com" },
            { icon: "instagram", url: "https://instagram.com" },
          ].map((s, i) => (
            <TouchableOpacity key={i} onPress={() => Linking.openURL(s.url)}>
              <View style={styles.socialBtn}>
                <FontAwesome name={s.icon as any} size={40} color="#555" />
              </View>
            </TouchableOpacity>
          ))}
        </View>

        <Text style={styles.sectionTitle}>Rate us</Text>
        <View style={styles.ratingRow}>
          {[1, 2, 3, 4, 5].map((i) => (
            <TouchableOpacity key={i} onPress={() => setRating(i)}>
              <FontAwesome
                name={i <= rating ? "star" : "star-o"}
                size={28}
                color="#E7A600"
                style={{ marginRight: 5 }}
              />
            </TouchableOpacity>
          ))}
        </View>
      </View>
      <Footer />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#FCF5E3",
    paddingTop: "10%",
  },
  innerContainer: {
    flex: 1,
    backgroundColor: "#F0F6D5",
    borderTopLeftRadius: 15,
    borderTopRightRadius: 15,
    padding: "5%",
    elevation: 10,
  },
  menuItem: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    borderWidth: 4,
    borderRadius: 25,
    padding: 14,
    marginBottom: 14,
  },
  sectionTitle: {
    fontSize: 22,
    fontWeight: "600",
    marginVertical: 10,
  },
  socialRow: {
    flexDirection: "row",
    gap: 15,
  },
  socialBtn: {
    width: 65,
    height: 65,
    borderRadius: 35,
    borderWidth: 2,
    borderColor: "#FFD966",
    backgroundColor: "#fff",
    justifyContent: "center",
    alignItems: "center",
  },
  ratingRow: {
    flexDirection: "row",
    marginTop: 8,
  },
});
