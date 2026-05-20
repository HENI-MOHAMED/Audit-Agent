import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Building2, Users, Briefcase, ShieldAlert, ArrowRight, ActivitySquare, AlertCircle } from "lucide-react";
import { initializeApp } from "firebase/app";
import { getAuth, signInWithEmailAndPassword, createUserWithEmailAndPassword } from "firebase/auth";

// ⚠️ Ensure you replace this with your actual Firebase config
const app = initializeApp({
  apiKey: "AIzaSyDRROmDTz_x4wdX6FqAdXRZ5vLI1FIYrZE",
  authDomain: "audit-agent-46355.firebaseapp.com ",
  projectId: "audit-agent-46355",
});
const auth = getAuth(app);

export default function LogIn() {
  const [role, setRole] = useState<string>("customer");
  const [showLogin, setShowLogin] = useState(false);
  const [isSignIn, setIsSignIn] = useState(true);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  const handleAuth = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      if (isSignIn) {
        await signInWithEmailAndPassword(auth, email, password);
      } else {
        await createUserWithEmailAndPassword(auth, email, password);
      }

      const user = auth.currentUser;
      if (user) {
        const idToken = await user.getIdToken(true); // force refresh to get claims
        const tokenResult = await user.getIdTokenResult();
        const customRole = tokenResult.claims.role || role; // fallback to selected role if not assigned yet
        
        localStorage.setItem("authToken", idToken);
        localStorage.setItem("userRole", customRole as string);
      } else {
        localStorage.setItem("userRole", role);
      }

      navigate("/dashboard");
    } catch (err: any) {
      if (err.code === 'auth/email-already-in-use') {
        setError("This email already exists. Please sign in instead.");
      } else if (err.code === 'auth/invalid-credential') {
        setError("Invalid email or password.");
      } else if (err.code === 'auth/weak-password') {
        setError("Password should be at least 6 characters.");
      } else {
        setError(err.message || "Authentication failed.");
      }
    }
  };

  if (!showLogin) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-slate-50 p-4">
        <div className="w-full max-w-md">
          <div className="flex items-center justify-center mb-8 gap-2 text-primary">
            <ActivitySquare className="h-8 w-8" />
            <span className="text-3xl font-bold tracking-tighter">AuditBuddy</span>
          </div>
          
          <Card className="border-0 shadow-xl overflow-hidden rounded-xl">
            <div className="h-2 bg-primary w-full" />
            <CardHeader className="space-y-3 pt-8 pb-6 px-8 text-center">
              <CardTitle className="text-2xl font-semibold">Welcome back</CardTitle>
              <CardDescription className="text-base">
                Please select your account type to continue
              </CardDescription>
            </CardHeader>
            <CardContent className="px-8 pb-8 space-y-6">
              <Select value={role} onValueChange={setRole}>
                <SelectTrigger className="w-full h-12 text-base">
                  <SelectValue placeholder="Select a role" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="customer">
                    <div className="flex items-center gap-2">
                      <Users className="h-4 w-4 text-green-500" /> Customer
                    </div>
                  </SelectItem>
                  <SelectItem value="supplier">
                    <div className="flex items-center gap-2">
                      <Building2 className="h-4 w-4 text-blue-500" /> Supplier
                    </div>
                  </SelectItem>
                  <SelectItem value="employee">
                    <div className="flex items-center gap-2">
                      <Briefcase className="h-4 w-4 text-orange-500" /> Employee
                    </div>
                  </SelectItem>
                  <SelectItem value="admin">
                    <div className="flex items-center gap-2">
                      <ShieldAlert className="h-4 w-4 text-red-500" /> Admin
                    </div>
                  </SelectItem>
                </SelectContent>
              </Select>
              
              <Button 
                onClick={() => setShowLogin(true)} 
                className="w-full h-12 text-base font-medium shadow-sm transition-all hover:translate-y-[-1px]"
              >
                Continue to sign in
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </CardContent>
            <CardFooter className="bg-slate-50 border-t px-8 py-4 justify-center">
              <p className="text-sm text-muted-foreground text-center">
                Secure enterprise auditing and compliance platform.
              </p>
            </CardFooter>
          </Card>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-slate-50 p-4">
      <div className="w-full max-w-md">
        <div className="flex items-center justify-center mb-8 gap-2 text-primary">
          <ActivitySquare className="h-8 w-8" />
          <span className="text-3xl font-bold tracking-tighter">AuditBuddy</span>
        </div>
        
        <Card className="border-0 shadow-xl overflow-hidden rounded-xl">
          <div className="h-2 bg-primary w-full" />
          <CardHeader className="space-y-1 pt-8 pb-2 px-8">
            <div className="flex items-center justify-between">
              <CardTitle className="text-2xl font-semibold">{isSignIn ? "Sign In" : "Sign Up"}</CardTitle>
              <Button 
                variant="ghost" 
                size="sm" 
                className="text-muted-foreground hover:text-foreground h-auto p-0" 
                onClick={() => {
                  setShowLogin(false);
                  setError(null);
                }}
              >
                Change role
              </Button>
            </div>
            <CardDescription className="capitalize flex items-center gap-1.5 text-base">
              Connecting as <span className="font-medium text-foreground">{role}</span>
            </CardDescription>
          </CardHeader>
          <CardContent className="px-8 pb-8 pt-4">
            <form onSubmit={handleAuth} className="space-y-4">
              {error && (
                <div className="flex items-center gap-2 text-sm text-red-600 bg-red-50 p-3 rounded-md border border-red-100">
                  <AlertCircle className="h-4 w-4 shrink-0" />
                  <span>{error}</span>
                </div>
              )}
              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <Input 
                  id="email" 
                  type="email" 
                  value={email} 
                  onChange={e => setEmail(e.target.value)} 
                  required 
                  className="h-10"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="password">Password</Label>
                <Input 
                  id="password" 
                  type="password" 
                  value={password} 
                  onChange={e => setPassword(e.target.value)} 
                  required 
                  className="h-10"
                />
              </div>
              <Button type="submit" className="w-full h-11 text-base mt-2">
                {isSignIn ? "Sign In" : "Create Account"}
              </Button>
              <div className="text-center mt-4 pt-2">
                <Button 
                  type="button" 
                  variant="link" 
                  className="text-sm text-muted-foreground hover:text-primary"
                  onClick={() => {
                    setIsSignIn(!isSignIn);
                    setError(null);
                  }}
                >
                  {isSignIn ? "Don't have an account? Sign up" : "Already have an account? Sign in"}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}