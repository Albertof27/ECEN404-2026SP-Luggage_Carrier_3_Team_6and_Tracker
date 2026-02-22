import 'package:firebase_auth/firebase_auth.dart';

/// Friendly auth error you can show directly in the UI.
class AuthException implements Exception {
  final String code;
  final String message;

  AuthException({required this.code, required this.message});

  @override
  String toString() => '$code: $message';
}

class AuthService {
  final FirebaseAuth _auth = FirebaseAuth.instance;

  Stream<User?> authStateChanges() => _auth.authStateChanges();

  Future<UserCredential> signIn(String email, String password) async {
    try {
      return await _auth.signInWithEmailAndPassword(
        email: email,
        password: password,
      );
    } on FirebaseAuthException catch (e) {
      throw AuthException(
        code: e.code,
        message: _mapFirebaseErrorToMessage(e),
      );
    }
  }

  Future<UserCredential> register(String email, String password) async {
    try {
      return await _auth.createUserWithEmailAndPassword(
        email: email,
        password: password,
      );
    } on FirebaseAuthException catch (e) {
      throw AuthException(
        code: e.code,
        message: _mapFirebaseErrorToMessage(e),
      );
    }
  }

  Future<void> sendPasswordReset(String email) async {
    try {
      await _auth.sendPasswordResetEmail(email: email);
    } on FirebaseAuthException catch (e) {
      throw AuthException(
        code: e.code,
        message: _mapFirebaseErrorToMessage(e),
      );
    }
  }

  Future<void> signOut() => _auth.signOut();

  // CENTRAL place to convert Firebase error codes -> pretty text
  String _mapFirebaseErrorToMessage(FirebaseAuthException e) {
    switch (e.code) {
      case 'invalid-email':
        return "That email address doesn’t look quite right. Double-check it and try again.";

      case 'user-not-found':
        return "We couldn’t find an account with this email. Try signing up instead.";

      case 'wrong-password':
        return "That password is incorrect. Try again, or tap “Forgot password?” to reset it.";

      case 'user-disabled':
        return "This account has been disabled. Please contact support if you think this is a mistake.";

      case 'email-already-in-use':
        return "An account with this email already exists. Try logging in instead.";

      case 'weak-password':
        return "Your password is a bit too weak. Please use at least 6 characters.";

      case 'too-many-requests':
        return "There have been too many attempts. Please wait a moment and try again.";

      case 'network-request-failed':
        return "We couldn’t reach the server. Please check your internet connection.";

      default:
        return "Something went wrong while signing you in. Please try again.";
    }
  }
}



/*
import 'package:firebase_auth/firebase_auth.dart';

class AuthService {
  final FirebaseAuth _auth = FirebaseAuth.instance;

  Stream<User?> authStateChanges() => _auth.authStateChanges();

  Future<UserCredential> signIn(String email, String password) {
    return _auth.signInWithEmailAndPassword(email: email, password: password);
  }

  Future<UserCredential> register(String email, String password) {
    return _auth.createUserWithEmailAndPassword(email: email, password: password);
  }

  Future<void> sendPasswordReset(String email) {
    return _auth.sendPasswordResetEmail(email: email);
  }

  Future<void> signOut() => _auth.signOut();
}
*/
